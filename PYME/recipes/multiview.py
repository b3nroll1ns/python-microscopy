from .base import register_module, ModuleBase, Filter
from .traits import Input, Output, Float, Enum, CStr, Bool, Int, List, DictStrStr, DictStrList, ListFloat, ListStr

import numpy as np
from PYME.IO import tabular


@register_module('Fold')
class Fold(ModuleBase):
    """
    Fold localizations from images which have been taken with an image splitting device but analysed without channel
    awareness. Images taken in this fashion will have the channels side by side. This module folds the x co-ordinate to
    overlay the different channels, using the image metadata to determine the appropriate ROI boundaries.

    The current implementation is somewhat limited as it only handles folding along the x axis, and assumes that ROI
    sizes and spacings are completely uniform.
    """
    input_name = Input('localizations')
    output_name = Output('folded')

    def execute(self, namespace):
        from PYME.Analysis.points import multiview

        inp = namespace[self.input_name]

        if 'mdh' not in dir(inp):
            raise RuntimeError('Unfold needs metadata')

        mapped = multiview.foldX(inp, inp.mdh)
        mapped.mdh = inp.mdh

        namespace[self.output_name] = mapped


@register_module('ShiftCorrect')
class ShiftCorrect(ModuleBase):
    """
    Applies chromatic shift correction to folded localization data that was acquired with an image splitting device,
    but localized without splitter awareness.

    Parameters
    ----------

    shift_map_path : str
        file path of shift map to be applied. Can also be a URL for shiftmaps stored remotely
    """
    input_name = Input('folded')
    shift_map_path = CStr('')
    output_name = Output('registered')

    def execute(self, namespace):
        from PYME.Analysis.points import multiview
        from PYME.IO import unifiedIO
        import json

        inp = namespace[self.input_name]

        if 'mdh' not in dir(inp):
            raise RuntimeError('ShiftCorrect needs metadata')

        if self.shift_map_path == '':  # grab shftmap from the metadata
            s = unifiedIO.read(inp.mdh['Shiftmap'])
        else:
            s = unifiedIO.read(self.shift_map_path)

        shiftMaps = json.loads(s)

        mapped = tabular.mappingFilter(inp)

        dx, dy = multiview.calcShifts(mapped, shiftMaps)
        mapped.addColumn('chromadx', dx)
        mapped.addColumn('chromady', dy)

        mapped.setMapping('x', 'x + chromadx')
        mapped.setMapping('y', 'y + chromady')

        mapped.mdh = inp.mdh

        namespace[self.output_name] = mapped


@register_module('FindClumps')
class FindClumps(ModuleBase):
    """Create a new mapping object which derives mapped keys from original ones"""
    input_name = Input('registered')
    gapTolerance = Int(1, desc='Number of off-frames allowed to still be a single clump')
    radiusScale = Float(2.0,
                        desc='Factor by which error_x is multiplied to detect clumps. The default of 2-sigma means we link ~95% of the points which should be linked')
    radius_offset = Float(0.,
                          desc='Extra offset (in nm) for cases where we want to link despite poor channel alignment')
    probeAware = Bool(False, desc='''Use probe-aware clumping. NB this option does not work with standard methods of colour
                                             specification, and splitting by channel and clumping separately is preferred''')
    output_name = Output('clumped')

    def execute(self, namespace):
        from PYME.Analysis.points import multiview

        inp = namespace[self.input_name]

        if self.probeAware and 'probe' in inp.keys():  # special case for using probe aware clumping NB this is a temporary fudge for non-standard colour handling
            mapped = multiview.find_clumps_within_channel(inp, self.gapTolerance, self.radiusScale, self.radius_offset)
        else:  # default
            mapped = multiview.find_clumps(inp, self.gapTolerance, self.radiusScale, self.radius_offset)

        if 'mdh' in dir(inp):
            mapped.mdh = inp.mdh

        namespace[self.output_name] = mapped


@register_module('MergeClumps')
class MergeClumps(ModuleBase):
    """Create a new mapping object which derives mapped keys from original ones"""
    input_name = Input('clumped')
    output_name = Output('merged')
    labelKey = CStr('clumpIndex')

    def execute(self, namespace):
        from PYME.Analysis.points import multiview

        inp = namespace[self.input_name]

        try:
            grouped = multiview.merge_clumps(inp, inp.mdh.getOrDefault('Multiview.NumROIs', 0), labelKey=self.labelKey)
            grouped.mdh = inp.mdh
        except AttributeError:
            grouped = multiview.merge_clumps(inp, numChan=0, labelKey=self.labelKey)

        namespace[self.output_name] = grouped


@register_module('MapAstigZ')
class MapAstigZ(ModuleBase):
    """Create a new mapping object which derives mapped keys from original ones"""
    input_name = Input('merged')

    astigmatismMapLocation = CStr('')  # FIXME - rename and possibly change type
    rough_knot_spacing = Float(50.)

    output_name = Output('zmapped')

    def execute(self, namespace):
        from PYME.Analysis.points.astigmatism import astigTools
        from PYME.IO import unifiedIO
        import json

        inp = namespace[self.input_name]

        if 'mdh' not in dir(inp):
            raise RuntimeError('MapAstigZ needs metadata')

        if self.astigmatismMapLocation == '':  # grab calibration from the metadata
            s = unifiedIO.read(inp.mdh['Analysis.AstigmatismMapID'])
        else:
            s = unifiedIO.read(self.astigmatismMapLocation)

        astig_calibrations = json.loads(s)

        mapped = tabular.mappingFilter(inp)

        z, zerr = astigTools.lookup_astig_z(mapped, astig_calibrations, self.rough_knot_spacing, plot=False)

        mapped.addColumn('astigZ', z)
        mapped.addColumn('zLookupError', zerr)
        mapped.setMapping('z', 'astigZ + z')

        mapped.mdh = inp.mdh

        namespace[self.output_name] = mapped

# ---------- calibration generation ----------

@register_module('CalibrateShifts')
class CalibrateShifts(ModuleBase):
    """

    Generates multiview shiftmaps from (folded) bead-data localizations. Only beads which show up in all channels are
    used to generate the shiftmaps

    Parameters
    ----------
    input_name : traits.Input
        localizations as PYME.IO.Tabular types
    search_radius_nm : traits.Float
        radius within which bead localizations should be clumped if the bead appears in all channels. Units of nm.

    Returns
    -------
    output_name : traits.Output
        output is a json wrapped by PYME.IO.ragged.RaggedCache

    Notes
    -----

    """
    input_name = Input('folded')

    search_radius_nm = Float(250.)

    output_name = Output('shiftmap')

    def execute(self, namespace):
        from PYME.Analysis.points import twoColour
        from PYME.Analysis.points import multiview
        from PYME.IO.MetaDataHandler import NestedClassMDHandler

        inp = namespace[self.input_name]

        try:  # make sure we're looking at multiview data
            n_chan = inp.mdh['Multiview.NumROIs']
        except AttributeError:
            raise AttributeError('multiview metadata is missing or incomplete')

        # sort in frame order
        I = inp['tIndex'].argsort()
        x_sort, y_sort = inp['x'][I], inp['y'][I]
        chan_sort = inp['multiviewChannel'][I]

        clump_id, keep = multiview.pair_molecules(inp['tIndex'][I], x_sort, y_sort, chan_sort,
                                                  self.search_radius_nm * np.ones_like(x_sort),
                                                  appear_in=np.arange(n_chan), n_frame_sep=inp['tIndex'].max(),
                                                  pix_size_nm=1e3 * inp.mdh['voxelsize.x'])

        # only look at the clumps which showed up in all channels
        x = x_sort[keep]
        y = y_sort[keep]
        chan = chan_sort[keep]
        clump_id = clump_id[keep]

        # Generate raw shift vectors (map of displacements between channels) for each channel
        mol_list = np.unique(clump_id)
        n_mols = len(mol_list)

        dx = np.zeros((n_chan - 1, n_mols))
        dy = np.zeros_like(dx)
        dx_err = np.zeros_like(dx)
        dy_err = np.zeros_like(dx)
        x_clump, y_clump, x_std, y_std, x_shifted, y_shifted = [], [], [], [], [], []

        shift_map_dtype = [('mx', '<f4'), ('mx2', '<f4'), ('mx3', '<f4'),  # x terms
                           ('my', '<f4'), ('my2', '<f4'), ('my3', '<f4'),  # y terms
                           ('mxy', '<f4'), ('mx2y', '<f4'), ('mxy2', '<f4'),  # cross terms
                           ('x0', '<f4')]  # 0th order shift

        shift_maps = np.zeros(2*(n_chan - 1), dtype=shift_map_dtype)
        mdh = NestedClassMDHandler(inp.mdh)
        mdh['shift_map.legend'] = {}

        for ii in range(n_chan):
            chan_mask = (chan == ii)
            x_chan = np.zeros(n_mols)
            y_chan = np.zeros(n_mols)
            x_chan_std = np.zeros(n_mols)
            y_chan_std = np.zeros(n_mols)

            for ind in range(n_mols):
                # merge clumps within channels
                clump_mask = np.where(np.logical_and(chan_mask, clump_id == mol_list[ind]))
                x_chan[ind] = x[clump_mask].mean()
                y_chan[ind] = y[clump_mask].mean()
                x_chan_std[ind] = x[clump_mask].std()
                y_chan_std[ind] = y[clump_mask].std()

            x_clump.append(x_chan)
            y_clump.append(y_chan)
            x_std.append(x_chan_std)
            y_std.append(y_chan_std)

            if ii > 0:
                dx[ii - 1, :] = x_clump[0] - x_clump[ii]
                dy[ii - 1, :] = y_clump[0] - y_clump[ii]
                dx_err[ii - 1, :] = np.sqrt(x_std[ii] ** 2 + x_std[0] ** 2)
                dy_err[ii - 1, :] = np.sqrt(y_std[ii] ** 2 + y_std[0] ** 2)
                # generate shiftmap between ii-th channel and the 0th channel
                dxx, dyy, spx, spy, good = twoColour.genShiftVectorFieldQ(x_clump[0], y_clump[0], dx[ii - 1, :],
                                                                          dy[ii - 1, :], dx_err[ii - 1, :],
                                                                          dy_err[ii - 1, :])
                # store shiftmaps in structured array
                mdh['shift_map.legend']['0%s_x' % ii] = 2*(ii - 1)
                mdh['shift_map.legend']['0%s_y' % ii] = 2*(ii - 1) + 1
                for ki in range(len(shift_map_dtype)):
                    k = shift_map_dtype[ki][0]
                    shift_maps[2*(ii - 1)][k] = spx.__getattribute__(k)
                    shift_maps[2*(ii - 1) + 1][k] = spy.__getattribute__(k)


                # shift_maps['Chan0%s.X' % ii], shift_maps['Chan0%s.Y' % ii] = spx.__dict__, spy.__dict__

        mdh['shift_map.model'] = '.'.join([spx.__class__.__module__, spx.__class__.__name__])

        namespace[self.output_name] = tabular.recArrayInput(shift_maps)
        namespace[self.output_name].mdh = mdh

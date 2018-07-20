from .base import register_module, ModuleBase, OutputModule
from .traits import Input, Output, Float, Enum, CStr, Bool, Int, DictStrStr

import numpy as np
import pandas as pd
import os
from PYME.IO import tabular

import logging
logger = logging.getLogger(__name__)

@register_module('CSVOutput')
class CSVOutput(OutputModule):
    """
    Save tabular data as csv.

    Parameters
    ----------

    inputName : basestring
        the name (in the recipe namespace) of the table to save.

    filePattern : basestring
        a pattern through which the output filename is generated by variable substitution (using `str.format`)

    scheme : enum
        The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
        and saves to a file on disk.

    Notes
    -----

    When using `File` or `pyme-cluster://` schemes, we convert the data to a pandas `DataFrame` and uses the `to_csv`
    method to save. When using `pyme-cluster:// - aggregate` we convert to a recarray and
    use `PYME.IO.clusterResults.fileResults`.

    pyme-cluster awareness
    ----------------------

    csv output is cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
    current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the
    processing node is also running a dataserver [TODO - make this more robust] .

    `pyme-cluster:// - aggregate` will **append** to a file on the cluster (creating if necessary). The intended usage
    of the aggregate scheme is allow the concatenation of summary results when a recipe is applied to multiple different
    source files. If subsequent identification of the source file, or e.g. metadata on sample conditions, this information
    should be added as a column to the tabular data before savine. See also `recipes.measurement.AddMetadataToMeasurements`.
    """

    inputName = Input('output')

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to CSV

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """

        out_filename = self.filePattern.format(**context)
        v = namespace[self.inputName]

        if self.scheme == 'pyme-cluster:// - aggregate':
            from PYME.IO import clusterResults
            clusterResults.fileResults('pyme-cluster://_aggregate_csv/' + out_filename.lstrip('/'), v.toDataFrame())
        else:
            out_filename = self._schemafy_filename(out_filename)
            if not isinstance(v, pd.DataFrame):
                v = v.toDataFrame()
                
            v.to_csv(out_filename)

@register_module('XLSXOutput')
class XLSOutput(OutputModule):
    """
    Save tabular data as xlsx.

    Parameters
    ----------

    inputName : basestring
        the name (in the recipe namespace) of the table to save.

    filePattern : basestring
        a pattern through which the output filename is generated by variable substitution (using `str.format`)

    scheme : enum
        The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
        and saves to a file on disk.

    Notes
    -----

    This casts the data to a pandas `DataFrame` and uses the `to_excel` method to save

    pyme-cluster awareness
    ----------------------

    xlsx output is semi cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
    current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the processing
    node is also running a dataserver [TODO - make this more robust] .

    `pyme-cluster:// - aggregate` is not supported.
    """
    inputName = Input('output')
    filePattern = '{output_dir}/{file_stub}.xlsx'

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to CSV

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """

        out_filename = self._schemafy_filename(self.filePattern.format(**context))

        v = namespace[self.inputName]
        v.toDataFrame.to_excel(out_filename)

@register_module('ImageOutput')
class ImageOutput(OutputModule):
    """
    Save an image with a file type determined by extension.

    Parameters
    ----------

    inputName : basestring
        the name (in the recipe namespace) of the image to save.

    filePattern : basestring
        a pattern through which the output filename is generated by variable substitution (using `str.format`)

    scheme : enum
        The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
        and saves to a file on disk.

    Notes
    -----

    This is a very thin wrapper which simply calls the `.save()` method on the `PYME.IO.image.ImageStack` object.

    pyme-cluster awareness
    ----------------------

    Image output is semi cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
    current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the processing
    node is also running a dataserver [TODO - make this more robust].

    `pyme-cluster:// - aggregate` is not supported.
    """
    inputName = Input('output')
    filePattern = '{output_dir}/{file_stub}.tif'
    
    def generate(self, namespace, recipe_context={}):
        return namespace[self.inputName]

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to CSV

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """

        out_filename = self._schemafy_filename(self.filePattern.format(**context))

        v = self.generate(namespace)
        v.Save(out_filename)


@register_module('HDFOutput')
class HDFOutput(OutputModule):
    """
        Save tabular data as a table in HDF5.

        Parameters
        ----------

        inputVariables : dict
            a dictionary mapping parameter names to table names

        filePattern : basestring
            a pattern through which the output filename is generated by variable substitution (using `str.format`)

        scheme : enum
            The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
            and saves to a file on disk.

        pyme-cluster awareness
        ----------------------

        csv output is cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
        current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the
        processing node is also running a dataserver [TODO - make this more robust] .

        `pyme-cluster:// - aggregate` will **append** to a file on the cluster (creating if necessary). The intended usage
        of the aggregate scheme is allow the concatenation of summary results when a recipe is applied to multiple different
        source files. If subsequent identification of the source file, or e.g. metadata on sample conditions, this information
        should be added as a column to the tabular data before savine. See also `recipes.measurement.AddMetadataToMeasurements`.
        """
    inputVariables = DictStrStr()
    filePattern = '{output_dir}/{file_stub}.hdf'

    @property
    def inputs(self):
        return set(self.inputVariables.keys())

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to HDF5

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """

        out_filename = self.filePattern.format(**context)

        if self.scheme == 'pyme-cluster:// - aggregate':
            from PYME.IO import clusterResults

            for name, h5_name in self.inputVariables.items():
                v = namespace[name]
                URI = '/'.join(['pyme-cluster:///_aggregate_h5r', out_filename.lstrip('/'), h5_name])
                clusterResults.fileResults(URI, v.to_recarray())
                #NOTE - aggregation does not support metadata
        else:
            out_filename = self._schemafy_filename(out_filename)

            for name, h5_name in self.inputVariables.items():
                v = namespace[name]
                v.to_hdf(out_filename, tablename=h5_name, metadata=getattr(v, 'mdh', None))

    @property
    def default_view(self):
        from traitsui.api import View, Item, Group
        from PYME.ui.custom_traits_editors import CBEditor

        editable = self.class_editable_traits()
        inputs = [tn for tn in editable if tn.startswith('input')]
        outputs = [tn for tn in editable if tn.startswith('output')]
        params = [tn for tn in editable if not (tn in inputs or tn in outputs or tn.startswith('_'))]

        return View([Item(tn) for tn in inputs] + [Item('_'), ] +
                    [Item(tn) for tn in params] + [Item('_'), ] +
                    [Item(tn) for tn in outputs], buttons=['OK', 'Cancel'])

#from jinja2 import Environment, PackageLoader
import jinja2
import os
class UnifiedLoader(jinja2.BaseLoader):
    def get_source(self, environment, template):
        from PYME.IO import unifiedIO
        try:
            if os.path.exists(os.path.join(os.path.dirname(__file__), template)):
                source = unifiedIO.read(os.path.join(os.path.dirname(__file__), template)).decode('utf-8')
            else:
                source = unifiedIO.read(template).decode('utf-8')
        except:
            logger.exception('Error loading template')
            raise jinja2.TemplateNotFound
        return source, template, lambda: False

env = jinja2.Environment(loader=UnifiedLoader())
from PYME.Analysis import graphing_filters #FIXME - move the filters somewhere better
import base64
env.filters['movieplot'] = graphing_filters.movieplot2
env.filters['plot'] = graphing_filters.plot
env.filters['b64encode'] = base64.b64encode

def round_sf(num, sf=3):
    import math

    fmt = '%' + ('.%d' % sf) + 'g'
    #rnd = float(fmt % f)
    rnd = round(num, sf - int(math.floor(math.log10(num))) - 1)
    if rnd > 1e6:
        return fmt % rnd
    elif rnd >= 10 ** sf:
        return '%d' % rnd
    else:
        fmt = '%' + ('.%d' % (sf - math.floor(math.log10(rnd)) - 1)) + 'f'
        return fmt % rnd
    
env.filters['roundsf'] = round_sf


@register_module('ReportOutput')
class ReportOutput(OutputModule):
    """
    Save an html report.

    Parameters
    ----------

    inputName : basestring
        the name (in the recipe namespace) of the image to save.

    filePattern : basestring
        a pattern through which the output filename is generated by variable substitution (using `str.format`)

    scheme : enum
        The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
        and saves to a file on disk.

    template : basestring
        The path / uri to the html template to use.

    Notes
    -----

    This is a very thin wrapper which simply calls the `.save()` method on the `PYME.IO.image.ImageStack` object.

    pyme-cluster awareness
    ----------------------

    report output is semi cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
    current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the processing
    node is also running a dataserver [TODO - make this more robust].

    `pyme-cluster:// - aggregate` is not supported.
    """
    inputName = Input('output')
    filePattern = '{output_dir}/{file_stub}.html'

    template = CStr('templates/report.html')
    
    def generate(self, namespace, recipe_context={}):
        template = env.get_template(self.template)
        v = namespace[self.inputName]
        return template.render(data=v, namespace=namespace, recipe_context=recipe_context)

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to CSV

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """
        import codecs

        out_filename = self._schemafy_filename(self.filePattern.format(**context))
        
        out_dir = os.path.dirname(out_filename)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        with open(out_filename, 'w') as f:
            f.write(self.generate(namespace, recipe_context=context).encode('utf-8'))


@register_module('ReportForEachOutput')
class ReportForEachOutput(OutputModule):
    """
    Save an html report for each item in a sequence.

    Parameters
    ----------

    inputName : basestring
        the name (in the recipe namespace) of the image to save.

    filePattern : basestring
        a pattern through which the output filename is generated by variable substitution (using `str.format`)

    scheme : enum
        The storage method, one of 'File', 'pyme-cluster://' or 'pyme-cluster:// - aggregate`. File is the default
        and saves to a file on disk.

    template : basestring
        The path / uri to the html template to use.

    Notes
    -----

    This is a very thin wrapper which simply calls the `.save()` method on the `PYME.IO.image.ImageStack` object.

    pyme-cluster awareness
    ----------------------

    report output is semi cluster-aware. Selecting a scheme of `pyme-cluster://` will save within the cluster root on the
    current machine, so that the results are accessible through the cluster. **NOTE:** this will **ONLY** work if the processing
    node is also running a dataserver [TODO - make this more robust].

    `pyme-cluster:// - aggregate` is not supported.
    """
    inputName = Input('output')
    inputImage = Input('')
    filePattern = '{output_dir}/{file_stub}_{num}.html'
    template = CStr('templates/report.html')

    def save(self, namespace, context={}):
        """
        Save recipes output(s) to CSV

        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to generate the output name. At least
            'basedir' (which is the fully resolved directory name in which the input file resides) and
            'filestub' (which is the filename without any extension) should be resolved.

        Returns
        -------

        """
        template = env.get_template(self.template)

        v = namespace[self.inputName]
        img = namespace[self.inputImage]

        for i, c in enumerate(v):
            out_filename = self._schemafy_filename(self.filePattern.format(num=i, **context))
            
            out_dir = os.path.dirname(out_filename)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            
            with open(out_filename, 'w') as f:
                f.write(template.render(data=c, img=img))

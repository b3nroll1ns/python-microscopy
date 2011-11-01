#!/usr/bin/python
##################
# objectMeasurements.py
#
# Copyright David Baddeley, 2011
# d.baddeley@auckland.ac.nz
# 
# This file may NOT be distributed without express permision from David Baddeley
#
##################

import wx
import numpy as np

class ParticleTracker:
    def __init__(self, visFr):
        self.visFr = visFr

        ID_GET_IDS = wx.NewId()
        visFr.extras_menu.Append(ID_GET_IDS, "Get segmented IDs from image")
        visFr.Bind(wx.EVT_MENU, self.OnGetIDs, id=ID_GET_IDS)

        ID_MEASURE = wx.NewId()
        visFr.extras_menu.Append(ID_MEASURE, "Measure objects")
        visFr.Bind(wx.EVT_MENU, self.OnMeasure, id=ID_MEASURE)

    def OnGetIDs(self, event):
        from PYME.DSView import image

        visFr = self.visFr

        dlg = wx.SingleChoiceDialog(
                self.visFr, 'choose the image which contains labels', 'Use Segmentation',
                image.openImages.keys(),
                wx.CHOICEDLG_STYLE
                )

        if dlg.ShowModal() == wx.ID_OK:
            img = image.openImages[dlg.GetStringSelection()]

            pixX = np.round((visFr.mapping['x'] - img.imgBounds.x0)/img.pixelSize).astype('i')
            pixY = np.round((visFr.mapping['y'] - img.imgBounds.y0)/img.pixelSize).astype('i')

            ind = (pixX < img.data.shape[0])*(pixY < img.data.shape[1])*(pixX >= 0)*(pixY >= 0)

            ids = np.zeros_like(pixX)
            #assume there is only one channel
            ids[ind] = img.data[:,:,:,0].squeeze()[pixX[ind], pixY[ind]].astype('i')

            numPerObject, b = np.histogram(ids, np.arange(ids.max() + 1.5) + .5)

            visFr.selectedDataSource.objectIDs = np.zeros(len(visFr.selectedDataSource['x']))
            visFr.selectedDataSource.objectIDs[visFr.filter.Index] = ids

            visFr.selectedDataSource.numPerObject = np.zeros(len(visFr.selectedDataSource['x']))
            visFr.selectedDataSource.numPerObject[visFr.filter.Index] = numPerObject[ids-1]

            visFr.selectedDataSource.setMapping('objectID', 'objectIDs')
            visFr.selectedDataSource.setMapping('NEvents', 'numPerObject')

            visFr.RegenFilter()
            visFr.CreateFoldPanel()

        dlg.Destroy()

    def OnMeasure(self, event):
        from PYME.Analysis.LMVis import objectMeasure

        chans = self.visFr.colourFilter.getColourChans()

        ids = set(self.visFr.mapping['objectID'].astype('i'))
        self.visFr.objectMeasures = {}

        if len(chans) == 0:
            self.visFr.objectMeasures['Everything'] = objectMeasure.measureObjectsByID(self.visFr.colourFilter, 10,ids)
        else:
            curChan = self.visFr.colourFilter.currentColour

            chanNames = chans[:]

#            if 'Sample.Labelling' in metadata.getEntryNames():
#                lab = metadata.getEntry('Sample.Labelling')
#
#                for i in range(len(lab)):
#                    if lab[i][0] in chanNames:
#                        chanNames[chanNames.index(lab[i][0])] = lab[i][1]

            for ch, i in zip(chans, range(len(chans))):
                self.visFr.colourFilter.setColour(ch)
                #fitDecayChan(colourFilter, metadata, chanNames[i], i)
                self.visFr.objectMeasures[chanNames[i]] = objectMeasure.measureObjectsByID(self.visFr.colourFilter, 10,ids)
            self.visFr.colourFilter.setColour(curChan)





def Plug(visFr):
    '''Plugs this module into the gui'''
    ParticleTracker(visFr)
# -*- coding: utf-8 -*-
"""
Created on Sat May 28 20:42:16 2016

@author: david
"""


#import datetime
#from PYME.Acquire import HDFSpooler, QueueSpooler
from PYME.Acquire import HTTPSpooler
# TODO: change to use a metadata handler / provideStartMetadata hook
#   MetaDataHandler.provideStartMetadata from the init file when
#   loading the sampleinfo interface, see Acquire/Scripts/init.py
try:
    from PYME.Acquire import sampleInformation
    sampInf = True
except:
    print('Could not connect to the sample information database')
    sampInf = False
#import win32api
from PYME.IO.FileUtils import nameUtils
from PYME.IO.FileUtils.nameUtils import numToAlpha, getRelFilename, genHDFDataFilepath
from PYME.IO import unifiedIO


#import PYME.Acquire.Protocols
import PYME.Acquire.protocol as prot
from PYME.Acquire.ui import preflight
from PYME import config

from PYME.misc import hybrid_ns

import os
import sys
#import glob

import subprocess
import threading
try:
    import queue
except ImportError:
    # py2, remove this when we can
    import Queue as queue

import dispatch

import logging
logger = logging.getLogger(__name__)

from PYME.util import webframework

class SpoolController(object):
    def __init__(self, scope, defDir=genHDFDataFilepath(), defSeries='%(day)d_%(month)d_series'):
        """Initialise the spooling controller.
        
        Parameters
        ----------
        scope : microscope instance
            The currently active microscope class (see microscope.py)
        defDir : string pattern
            The default directory to save data to. Any keys of the form `%(<key>)` 
            will be substituted using the values defined in `PYME.fileUtils.nameUtils.dateDict` 
        defSeries : string pattern
            This specifies a pattern for file naming. Keys will be substituted as for `defDir`
            
        """
        self.scope = scope
        
        if int(sys.version[0]) < 3:
            #default to Queue for Py2
            self.spoolType = 'Queue'
        else:
            #else default to file
            self.spoolType = 'File'
        
        #dtn = datetime.datetime.now()
        
        #dateDict = {'username' : win32api.GetUserName(), 'day' : dtn.day, 'month' : dtn.month, 'year':dtn.year}
        
        self._user_dir = None
        self._base_dir = nameUtils.get_local_data_directory()
        self._subdir = nameUtils.get_spool_subdir()
        self.seriesStub = defSeries % nameUtils.dateDict

        self.seriesCounter = 0
        self._series_name = None

        self.protocol = prot.NullProtocol
        self.protocolZ = prot.NullZProtocol
        
        self.onSpoolProgress = dispatch.Signal()
        self.onSpoolStart = dispatch.Signal()
        self.onSpoolStop = dispatch.Signal()

        self._analysis_launchers = queue.Queue(3)
        
        self._status_changed_condition = threading.Condition()
        
        #settings which were managed by GUI
        self.hdf_compression_level = 2 # zlib compression level that pytables should use (spool to file and queue)
        self.z_stepped = False  # z-step during acquisition
        self.z_dwell = 100 # time to spend at each z level (if z_stepped == True)
        self.cluster_h5 = False # spool to h5 on cluster (cluster of one)
        self.pzf_compression_settings=HTTPSpooler.defaultCompSettings # only for cluster spooling

        #check to see if we have a cluster
        self._N_data_servers = len(hybrid_ns.getNS('_pyme-http').get_advertised_services())
        if self._N_data_servers > 0:
            # switch to cluster as spool method if available.
            self.SetSpoolMethod('Cluster')
            
        if self._N_data_servers  == 1:
            self.cluster_h5 = True # we have a cluster of one
            
    @property
    def available_spool_methods(self):
        if int(sys.version[0]) < 3:
            return ['File', 'Queue', 'Cluster']
        else:
            return ['File', 'Cluster']
        
    def get_info(self):
        info =  {'settings' : {'method' : self.spoolType,
                                'hdf_compression_level': self.hdf_compression_level,
                                'z_stepped' : self.z_stepped,
                                'z_dwell' : self.z_dwell,
                                'cluster_h5' : self.cluster_h5,
                                'pzf_compression_settings' : self.pzf_compression_settings,
                                'protocol_name' : self.protocol.filename,
                                'series_name' : self.seriesName
                              },
                 'available_spool_methods' : self.available_spool_methods
                }
        
        try:
            info['status'] = self.spooler.status()
        except AttributeError:
            info['status'] = {'spooling':False}
        
        return info
    
    def update_settings(self, settings):
        method = settings.pop('method', None)
        if method:
            self.SetSpoolMethod(method)
        
        protocol_name = settings.pop('protocol_name', None)
        if protocol_name:
            self.SetProtocol(protocol_name)
            
        pzf_settings = settings.pop('pzf_compression_settings', None)
        if pzf_settings:
            self.pzf_compression_settings = dict(pzf_settings)
            
        for k, v in settings.items():
            setattr(self, k, v)
        
            
            
        
    @property
    def _sep(self):
        if self.spoolType == 'Cluster':
            return '/'
        else:
            return os.sep
        
    @property
    def dirname(self):
        if self.spoolType == 'Cluster':
            dir = self.get_cluster_dirname(self._user_dir) if self._user_dir is not None else '/'.join(self._subdir)
        else:
            dir = self._user_dir if self._user_dir is not None else os.sep.join([self._base_dir, ] + self._subdir)
        return dir

    def get_cluster_dirname(self, dirname):
        # Typically we'll be below the base directory, which we want to remove
        dir = dirname.replace(self._base_dir + os.sep, '')
        # if we weren't below PYMEData dir, which probably isn't great, at least drop any windows nonsense
        dir = dir.split(':')[-1]
        return unifiedIO.fix_name(dir.replace(os.sep, '/'))
        
    @property
    def seriesName(self):
        # make this a property so that we can defer evaluation to first use
        # this lets us set 'acquire-spool_subdirectories' in the init.py for a specific microscope
        if self._series_name is None:
            #if we've had to quit for whatever reason start where we left off
            #while os.path.exists(os.path.join(self.dirname, self.seriesName + '.h5')):
            self._series_name = self._GenSeriesName()
            self._update_series_counter()
        
        return self._series_name
    
    @seriesName.setter
    def seriesName(self, val):
        self._series_name = val
    

    def _GenSeriesName(self):
        if config.get('acquire-spool_subdirectories', False):
            # High-throughput performance optimization
            # If true, add a layer of directories to limit the number of series saved in a single directory
            return '%03d%s%s_%05d' % (int(self.seriesCounter/100), self._sep, self.seriesStub, self.seriesCounter)
        else:
            return self.seriesStub + '_' + numToAlpha(self.seriesCounter)
       
    def _checkOutputExists(self, fn):
        if self.spoolType == 'Cluster':
            from PYME.Acquire import HTTPSpooler
            # special case for HTTP spooling.  Make sure 000\series.pcs -> 000/series.pcs
            pyme_cluster = self.dirname + '/' + fn.replace('\\', '/')
            logger.debug('Looking for %s (.pcs or .h5) on cluster' % pyme_cluster)
            return HTTPSpooler.exists(pyme_cluster + '.pcs') or HTTPSpooler.exists(pyme_cluster + '.h5')
            #return (fn + '.h5/') in HTTPSpooler.clusterIO.listdir(self.dirname)
        else:
            local_h5 = os.sep.join([self.dirname, fn + '.h5'])
            logger.debug('Looking for %s on local machine' % local_h5)
            return os.path.exists(local_h5)
        
    def get_free_space(self):
        """
        Get available space in the target spool directory
        
        Returns
        -------
        
        free space in GB

        """
        if self.spoolType == 'Cluster':
            #logger.warn('Cluster free space calculation not yet implemented, using fake value')
            # FIXME - make free space calculations work on cluster (warning above commented out for Andrew's sanity)
            return float('nan')
        else:
            from PYME.IO.FileUtils.freeSpace import get_free_space
            return get_free_space(self.dirname)/1e9
        
    def _update_series_counter(self):
        logger.debug('Updating series counter')
        while self._checkOutputExists(self.seriesName):
            self.seriesCounter +=1
            self.seriesName = self._GenSeriesName()
            
    def SetSpoolDir(self, dirname):
        """Set the directory we're spooling into"""
        self._user_dir = dirname + os.sep
        #if we've had to quit for whatever reason start where we left off
        self._update_series_counter()
            
    def _ProgressUpate(self, **kwargs):
        with self._status_changed_condition:
            self._status_changed_condition.notify_all()
            
        self.onSpoolProgress.send(self)
        
    def _get_queue_name(self, fn, pcs=False):
        if pcs:
            ext = '.pcs'
        else:
            ext = '.h5'
            
        return self._sep.join([self.dirname.rstrip(self._sep), fn + ext])


    @webframework.register_endpoint('/start_spooling')
    def StartSpooling(self, fn=None, stack=False, compLevel = 2, zDwellTime = None, doPreflightCheck=True, maxFrames = sys.maxsize,
                      pzf_compression_settings=None, cluster_h5 = False):
        """Start spooling
        """
        
        # these settings were managed by the GUI, but are now managed by the controller, still allow them to be passed in,
        # but default to using our internal values
        compLevel = self.hdf_compression_level if compLevel is None else compLevel
        pzf_compression_settings = self.pzf_compression_settings if pzf_compression_settings is None else pzf_compression_settings
        stack = self.z_stepped if stack is None else stack
        cluster_h5 = self.cluster_h5 if cluster_h5 is None else cluster_h5
        fn = self.seriesName if fn in ['', None] else fn
        zDwellTime = self.z_dwell if zDwellTime is None else zDwellTime
        
        #make directories as needed
        if not (self.spoolType == 'Cluster'):
            dirname = os.path.split(self._get_queue_name(fn))[0]
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        if self._checkOutputExists(fn): #check to see if data with the same name exists
            self.seriesCounter +=1
            self.seriesName = self._GenSeriesName()
            
            raise IOError('Output file already exists')

        if stack:
            protocol = self.protocolZ
            if not zDwellTime is None:
                protocol.dwellTime = zDwellTime
            print(protocol)
        else:
            protocol = self.protocol

        if doPreflightCheck and not preflight.ShowPreflightResults(None, self.protocol.PreflightCheck()):
            return #bail if we failed the pre flight check, and the user didn't choose to continue
            
          
        #fix timing when using fake camera
        if self.scope.cam.__class__.__name__ == 'FakeCamera':
            fakeCycleTime = self.scope.cam.GetIntegTime()
        else:
            fakeCycleTime = None
            
        frameShape = (self.scope.cam.GetPicWidth(), self.scope.cam.GetPicHeight())
        
        if self.spoolType == 'Queue':
            from PYME.Acquire import QueueSpooler
            self.queueName = getRelFilename(self._get_queue_name(fn))
            self.spooler = QueueSpooler.Spooler(self.queueName, self.scope.frameWrangler.onFrame, 
                                                frameShape = frameShape, protocol=protocol, 
                                                guiUpdateCallback=self._ProgressUpate, complevel=compLevel, 
                                                fakeCamCycleTime=fakeCycleTime, maxFrames=maxFrames)
        elif self.spoolType == 'Cluster':
            from PYME.Acquire import HTTPSpooler
            self.queueName = self._get_queue_name(fn, pcs=(not cluster_h5))
            self.spooler = HTTPSpooler.Spooler(self.queueName, self.scope.frameWrangler.onFrame,
                                               frameShape = frameShape, protocol=protocol,
                                               guiUpdateCallback=self._ProgressUpate, complevel=compLevel,
                                               fakeCamCycleTime=fakeCycleTime, maxFrames=maxFrames,
                                               compressionSettings=pzf_compression_settings, aggregate_h5=cluster_h5)
           
        else:
            from PYME.Acquire import HDFSpooler
            self.spooler = HDFSpooler.Spooler(self._get_queue_name(fn), self.scope.frameWrangler.onFrame,
                                              frameShape = frameShape, protocol=protocol, 
                                              guiUpdateCallback=self._ProgressUpate, complevel=compLevel, 
                                              fakeCamCycleTime=fakeCycleTime, maxFrames=maxFrames)

        #TODO - sample info is probably better handled with a metadata hook
        #if sampInf:
        #    try:
        #        sampleInformation.getSampleData(self, self.spooler.md)
        #    except:
        #        #the connection to the database will timeout if not present
        #        #FIXME: catch the right exception (or delegate handling to sampleInformation module)
        #        pass
            
        self.spooler.onSpoolStop.connect(self.SpoolStopped)
        self.spooler.StartSpool()
        
        self.onSpoolStart.send(self)
        
        #return a function which can be called to indicate if we are done
        return lambda : not self.spooler.spoolOn

    @property
    def rel_dirname(self):
        return self._sep.join(self._subdir)

    def StopSpooling(self):
        """GUI callback to stop spooling."""
        self.spooler.StopSpool()
        
    def SpoolStopped(self, **kwargs):
        self.seriesCounter +=1
        self.seriesName = self._GenSeriesName()
        
        self.onSpoolStop.send(self)
        
    @property
    def autostart_analysis(self):
        if 'analysisSettings' in dir(self.scope):
            return self.scope.analysisSettings.propagateToAcquisisitonMetadata
        else:
            return False
        

    def LaunchAnalysis(self):
        """Launch analysis
        """
        from PYME.Acquire import QueueSpooler, HTTPSpooler
        
        dh5view_cmd = 'dh5view'
        if sys.platform == 'win32':
            dh5view_cmd = 'dh5view.exe'
            
        if self.autostart_analysis:
            dh5view_cmd += ' -g'
        
        if isinstance(self.spooler, QueueSpooler.Spooler): #queue or not
            subprocess.Popen('%s -q %s QUEUE://%s' % (dh5view_cmd, self.spooler.tq.URI, self.queueName), shell=True)
        elif isinstance(self.spooler, HTTPSpooler.Spooler): #queue or not
            if self.autostart_analysis:
                # launch analysis in a separate thread
                t = threading.Thread(target=self.launch_cluster_analysis)
                t.start()
                # keep track of a couple launching threads to make sure they have ample time to finish before joining
                if self._analysis_launchers.full():
                    self._analysis_launchers.get().join()
                self._analysis_launchers.put(t)
            else:
                subprocess.Popen('%s %s' % (dh5view_cmd, self.spooler.getURL()), shell=True)
     
    def launch_cluster_analysis(self):
        from PYME.cluster import HTTPRulePusher
        
        seriesName = self.spooler.getURL()
        try:
            HTTPRulePusher.launch_localize(self.scope.analysisSettings.analysisMDH, seriesName)
        except:
            logger.exception('Error launching analysis for %s' % seriesName)


    def SetProtocol(self, protocolName=None, reloadProtocol=True):
        """Set the current protocol .
        
        See also: PYME.Acquire.Protocols."""

        if (protocolName is None) or (protocolName == '<None>'):
            self.protocol = prot.NullProtocol
            self.protocolZ = prot.NullZProtocol
        else:
            #pmod = __import__('PYME.Acquire.Protocols.' + protocolName.split('.')[0],fromlist=['PYME', 'Acquire','Protocols'])
            
            #if reloadProtocol:
            #    reload(pmod) #force module to be reloaded so that changes in the protocol will be recognised
            pmod = prot.get_protocol(protocol_name=protocolName, reloadProtocol=reloadProtocol)

            self.protocol = pmod.PROTOCOL
            self.protocol.filename = protocolName
            
            self.protocolZ = pmod.PROTOCOL_STACK
            self.protocolZ.filename = protocolName
            
    def SetSpoolMethod(self, method):
        """Set the spooling method
        
        Parameters
        ----------
        
        method : string
            One of 'File', 'Queue', or 'HTTP'
        """
        self.spoolType = method
        self._update_series_counter()

    def __del__(self):
        # make sure our analysis launchers have a chance to finish their job before exiting
        while not self._analysis_launchers.empty():
            self._analysis_launchers.get().join()
            


class SpoolControllerWrapper(object):
    def __init__(self, spool_controller):
        self.spool_controller = spool_controller # type: SpoolController

    @webframework.register_endpoint('/info', output_is_json=False)
    def info(self):
        return self.spool_controller.get_info()

    @webframework.register_endpoint('/info_longpoll', output_is_json=False)
    def info_longpoll(self):
        with self.spool_controller._status_changed_condition:
            return self.spool_controller.get_info()

    @webframework.register_endpoint('/settings', output_is_json=False)
    def settings(self, body):
        import json
        try:
            self.spool_controller.update_settings(json.loads(body))
            return 'OK'
        except:
            logger.exception('Error setting spool controller settings')
            return 'Failure'

    @webframework.register_endpoint('/stop_spooling', output_is_json=False)
    def stop_spooling(self):
        self.spool_controller.StopSpooling()
        return 'OK'

    @webframework.register_endpoint('/start_spooling', output_is_json=False)
    def start_spooling(self, filename=None, max_frames=sys.maxsize):
        self.spool_controller.StartSpooling(fn=filename, maxFrames=max_frames)
        return 'OK'
        
    
        
    
    
    


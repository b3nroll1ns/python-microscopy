# -*- coding: utf-8 -*-
"""
Created on Fri Apr 05 11:57:53 2013

@author: David Baddeley
"""
from PYME.misc import lzw
import numpy as np

import read_agf

def decompZar(filename):
    '''zemax .zar files are a series of concatenated, LZW compressed text-format 
    files.
    
    This function attempts to locate and decompress each of the sections, returning
    a dictionary of strings where the keys are the origninal(uncompressed) file names.    
    ''' 
    f = open(filename, 'rb')
    raw = f.read()
    f.close()
    
    #delimiter seems to be first 4 bytes
    delim = raw[:4]
    
    #sections seem to be separated by at least 4 nulls, often more
    #the length comparison deals with multiple consecutive nulls
    sections = [s for s in raw.split('\0\0\0\0') if len(s) > 0]
    
    componentFiles = {}
    
    for i, s in enumerate(sections):
        #compressed data is preceeded by a plain-text file name
        if s.endswith('.LZW'):
            #this is a filename
            compFName = s[:-4]
            
            compData = ''.join([c for c in lzw.decompress(sections[i+1].lstrip('\0'))])
            
            componentFiles[compFName] = compData
        elif len(s) < 256:
            try: 
                #print s
                s = (s.lstrip('\0') + '\0').decode('utf16')
            except:
                s = ''
                
            #print s.encode('ascii', 'replace')
            if s.endswith('.LZW'):
                compFName = s[:-4]
        
                compData = ''.join([c for c in lzw.decompress(sections[i+1].lstrip('\0'))])
                
                if (len(compData) % 2):
                    #make sure we can decode as utf16
                    compData+='\0'
                compData = compData.decode('utf16').encode('ascii', 'replace')
                
                componentFiles[compFName] = compData
            
    return componentFiles
 
   
class DefaultGlass(object):
    #for compatibility with pyoptic
    mirror  = 1
    refract = 2
    
    def __init__(self, n=1.0, typ=2) :
        self.type = typ
        self.data = {'name':'air'}
        self._n = n
    
    def __str__(self) :
        return   'Material                 : ' + self.data['name']+'\n'

        
    def n(self, wavelength):
        return self._n
        
AIR = DefaultGlass()
    
class Glass(DefaultGlass):
    def __init__(self, data, typ=2) :

        self.type = typ
        self.data = data
        self.ns = {}
    
    def n(self, wavelength):
        #cache our refractive index to avoid un-necessary calculation
        try:
            n = self.ns[wavelength]
        except KeyError:
            n = read_agf.get_index(self.data, wavelength)
            self.ns[wavelength] = n
        
        return n
    
class Surface(object):
    def __init__(self, lines, glasses):
        self.glassName=None
        self.glass = AIR
        self.parseLines(lines, glasses)
        
        
    
    def parseLines(self, lines, glasses):
        while (len(lines) > 0) and lines[0].startswith('  '):
            l = lines.pop(0)
            l = l.lstrip()
            code = l[:4]
            data = l[5:]
            if code == 'TYPE':
                self.type = data
            elif code == 'CURV':
                self.curv = data.split()
                c = float(self.curv[0])
                if not c == 0:
                    self.radius = 1./float(self.curv[0])
                else:
                    self.radius = None
            elif code == 'GLAS':
                self.glas = data.split()
                self.glassName = self.glas[0]
                self.glass = Glass(glasses[self.glassName])
            elif code == 'DISZ':
                self.disz = float(data)
            elif code == 'DIAM':
                self.diam = data.split()
                self.diameter = float(self.diam[0])
                

    
class ZMX(object):
    def __init__(self, data, glasses):
        self.surfaces = []
        self._parseZMX(data, glasses)
        
        
    def _parseZMX(self,data, glasses):
        lines = data.splitlines()
        while len(lines) > 0:
            l = lines.pop(0)
            if l.startswith('SURF'):
                self.surfaces.append(Surface(lines, glasses))  
                
    def toPyOptic(self, position, direction=[0,0,1]):
        from pyoptic import System as pyo
        #we're only interested in real surfaces
        surfs = self.surfaces[1:-1]
        
        d = np.array(direction)
        pos = np.array(position)
        
        #calculate length of lens
        l = sum([s.disz for s in surfs[:-1]])
        
        outSurfs = []
        #midpoint at l/2
        z0 = -l/2
        for i, s in enumerate(surfs):
            outSurfs.append(pyo.SphericalSurface('ZMX_%d'%i, 1,np.ones(3)*float(s.diam[0]),pyo.Placement((z0 - 0)*d + pos,d),s.glass, s.radius))
            z0 += s.disz
            
        return outSurfs
        
                
def readZar(filename):
    components = decompZar(filename)
    
    glasses = {}
    
    #find all the glass catalogs    
    glass_cats = [n for n in components.keys() if n.endswith('.AGF')]
    for gc in glass_cats:
        glasses.update(read_agf.read_cat_from_string(components[gc]))
        
    print glasses.keys()
        
    #find all components (probably only one)
    zmxs = [ZMX(components[n], glasses) for n in components.keys() if (n.endswith('.ZMX') or n.endswith('.zmx'))]
    
    return zmxs, glasses
            
    
    
    
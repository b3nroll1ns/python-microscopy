#!/usr/bin/python

##################
# _fithelpers.py
#
# Copyright David Baddeley, 2009
# d.baddeley@auckland.ac.nz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##################

import scipy
import scipy.optimize as optimize
import numpy as np

FWHM_CONV_FACTOR = 2*scipy.sqrt(2*scipy.log(2))

EPS_FCN = 1e-5

def missfit(p, fcn, data, *args):
    """Helper function which evaluates a model function (fcn) with parameters (p) and additional arguments
    (*args) and compares this with measured data (data)"""
    return data - fcn(p, *args).ravel()

def weightedMissfit(p, fcn, data, sigmas, *args):
    """Helper function which evaluates a model function (fcn) with parameters (p) and additional arguments
    (*args) and compares this with measured data (data), scaling with the errors in the measured data (sigmas)"""
    mod = fcn(p, *args).ravel()
    #print mod.shape
    #print data.shape
    #print sigmas.shape
    return (data - mod)/sigmas

def weightedMissfitF(p, fcn, data, weights, *args):
    """Helper function which evaluates a model function (fcn) with parameters (p) and additional arguments
    (*args) and compares this with measured data (data), scaling with precomputed weights corresponding to the errors in the measured data (weights)"""
    mod = fcn(p, *args)
    mod = mod.ravel()
    #print mod.shape
    #print data.shape
    #print sigmas.shape
    return (data - mod)*weights  

def weightedJacF(p, fcn, data, weights, *args):
    """Helper function which evaluates a model function (fcn) with parameters (p) and additional arguments
    (*args) and compares this with measured data (data), scaling with precomputed weights corresponding to the errors in the measured data (weights)"""
    r = weights[:,None]*fcn.D(p, *args)
    return -r
    

def FitModel(modelFcn, startParameters, data, *args):
    return optimize.leastsq(missfit, startParameters, (modelFcn, data.ravel()) + args, full_output=1)

def FitModel_(modelFcn, startParameters, data, *args):
    return optimize.leastsq(missfit, startParameters, (modelFcn, data.ravel()) + args, full_output=1, epsfcn=EPS_FCN)

def FitModelWeighted(modelFcn, startParameters, data, sigmas, *args):
    return optimize.leastsq(weightedMissfitF, startParameters, (modelFcn, data.ravel(), (1.0/sigmas).astype('f').ravel()) + args, full_output=1)

def FitModelWeighted_(modelFcn, startParameters, data, sigmas, *args):
    return optimize.leastsq(weightedMissfitF, startParameters, (modelFcn, data.ravel(), (1.0/sigmas).astype('f').ravel()) + args, full_output=1, epsfcn=EPS_FCN)

def FitModelWeightedJac(modelFcn, startParameters, data, sigmas, *args):
    return optimize.leastsq(weightedMissfitF, startParameters, (modelFcn, data.ravel(), (1.0/sigmas).astype('d').ravel()) + args, Dfun = weightedJacF, full_output=1, col_deriv = 0)
    
def FitModelWeightedJac_(modelFcn, startParameters, data, sigmas, *args):
    return optimize.leastsq(weightedMissfitF, startParameters, (modelFcn, data.ravel(), (1.0/sigmas).astype('d').ravel()) + args, Dfun = weightedJacF, full_output=1, col_deriv = 0, epsfcn=EPS_FCN)


def FitWeightedMisfitFcn(misfitFcn, startParameters, data, sigmas, *args):
    return optimize.leastsq(misfitFcn, np.array(startParameters), (np.array(data, order='F'), np.array(1.0/sigmas, order='F')) + args, full_output=1)
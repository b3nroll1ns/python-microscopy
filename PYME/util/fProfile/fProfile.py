#!/usr/bin/python

###############
# mProfile.py
#
# Copyright David Baddeley, 2012
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
################
#!/usr/bin/python
""" mProfile.py - Matlab(TM) style line based profiling for Python

Copyright: David Baddeley 2008
	   david_baddeley <at> yahoo.com.au

useage is similar to profiling in matlab (profile on, profile off, report),
with the major difference being that you have to specify the filenames in which
you want to do the profiling (to improve performance & to save wading through
lots of standard library code etc ...).

e.g.

mProfile.profileOn(['onefile.py', 'anotherfile.py'])

stuff to be profiled ....

mProfile.profileOff()
mProfile.report()

Due to the fact that we're doing this in python, and hooking every line, 
there is a substantial performance hit, although for the numeric code I wrote it
for (lots of vectorised numpy/scipy stuff) it's only on the order of ~30%.

Licensing: Take your pick of BSD or GPL
"""

import sys
import time

#import os
#import colorize_db_t
#import webbrowser
#import tempfile

import threading
try:
    import Queue
except ImportError:
    import queue as Queue

import re

import site

lib_prefix = site.getsitepackages()[0]
len_lib_prefix = len(lib_prefix)

class thread_profiler(object):
    def __init__(self):
        self.outfile = None
        
        self._do_poll = True
        self._out_queue = Queue.Queue()

    def profileOn(self, regex='.*PYME.*', outfile='profile.txt'):
        self.regex = re.compile(regex)
        self.outfile = open(outfile, 'w')

        sys.setprofile(self.prof_callback)
        threading.setprofile(self.prof_callback)
        
        self._tPoll = threading.Thread(target=self._poll)
        self._tPoll.start()



    def profileOff(self):
        sys.setprofile(None)
        threading.setprofile(None)
        
        self._do_poll = False
        self._tPoll.join()

        self.outfile.flush()
        self.outfile.close()
        
        
    def _poll(self):
        while self._do_poll:
            self.outfile.write(self._out_queue.get(timeout=0.1))

    def prof_callback(self, frame, event, arg):
        if event in ['call', 'return'] and (not frame.f_code.co_filename == __file__) and self.regex.match(frame.f_code.co_filename):
            fn = frame.f_code.co_filename #.split(os.sep)[-1]
            if fn.startswith(lib_prefix):
                fn = fn[len_lib_prefix:]

            funcName = fn + '\t' + frame.f_code.co_name
            #stack = '.'.join(frame.f_code.co_names)
            stack = frame.f_code.co_firstlineno #frame.f_back.f_code.co_name

            t = time.clock()

            self._out_queue.put('%f\t%s\t%s\t%s\t%s\n' % (t, threading.current_thread().getName(), funcName, event, stack))


        

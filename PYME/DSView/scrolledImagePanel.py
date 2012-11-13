#!/usr/bin/python

##################
# viewpanel.py
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

import wx

class ImagePanel(wx.Panel):
    def __init__(self, parent, renderer, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        self.parent = parent
        self.renderer = renderer


        wx.EVT_PAINT(self, self.OnPaint)
        wx.EVT_ERASE_BACKGROUND(self, self.DoNix)

    def DoNix(self, event):
        pass

    def OnPaint(self,event):
        DC = wx.PaintDC(self)
        self.PrepareDC(DC)
        
        s = self.GetClientSize()
        MemBitmap = wx.EmptyBitmap(s.GetWidth(), s.GetHeight())
        MemDC = wx.MemoryDC()
        OldBitmap = MemDC.SelectObject(MemBitmap)
        try:
            DC.BeginDrawing()
            
            self.renderer(MemDC);
            DC.Blit(0, 0, s.GetWidth(), s.GetHeight(), MemDC, 0, 0)
            DC.EndDrawing()
        finally:
            del MemDC
            del MemBitmap

 


class ScrolledImagePanel(wx.Panel):
    def __init__(self, parent, renderer,*args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        self.parent = parent
        
        self.imSize = (0,0)
        self.xOff = 0
        self.yOff = 0

        self.scrollRangeX = 0
        self.scrollRangeY = 0

        gridSizer = wx.FlexGridSizer(2)

        self.imagepanel = ImagePanel(self, renderer, -1, size = self.Size)
        gridSizer.Add(self.imagepanel, 1, wx.EXPAND, 0)

        self.scrollY = wx.ScrollBar(self, -1, style=wx.SB_VERTICAL)
        gridSizer.Add(self.scrollY, 0, wx.EXPAND, 0)

        self.scrollX = wx.ScrollBar(self, -1)
        gridSizer.Add(self.scrollX, 0, wx.EXPAND, 0)

        gridSizer.AddGrowableRow(0)
        gridSizer.AddGrowableCol(0)

        self.SetSizer(gridSizer)

        self.scrollX.Bind(wx.EVT_COMMAND_SCROLL, self.OnScrollX)
        self.scrollY.Bind(wx.EVT_COMMAND_SCROLL, self.OnScrollY)

        wx.EVT_SIZE(self, self.OnSize)


    def CalcUnscrolledPosition(self, x, y):
        return x + self.xOff, y + self.yOff

    def SetVirtualSize(self,size):
        self.imSize = size
        
        self.RefreshScrollbars()


    def RefreshScrollbars(self):
        self.scrollRangeX = max(0, self.imSize[0] - self.imagepanel.Size[0])
        self.xOff = min(self.xOff, self.scrollRangeX)
        #self.scrollX.SetScrollbar(self.xOff, max(1,  self.scrollRangeX*self.imagepanel.Size[0]/max(1, self.imSize[0])), self.scrollRangeX, 10)
        self.scrollX.SetScrollbar(self.xOff, 1, self.scrollRangeX, 10)

        self.scrollRangeY = max(0, self.imSize[1] - self.imagepanel.Size[1])
        self.yOff = min(self.yOff, self.scrollRangeY)
        #self.scrollY.SetScrollbar(self.yOff, max(1,  self.scrollRangeY*self.imagepanel.Size[1]/max(1, self.imSize[1])), self.scrollRangeY, 10)
        self.scrollY.SetScrollbar(self.yOff, 1, self.scrollRangeY, 10)

        if self.imSize[0] < self.imagepanel.Size[0]: #don't need scrollbar
            self.scrollX.Hide()
        else:
            self.scrollX.Show()

        if self.imSize[1] < self.imagepanel.Size[1]: #don't need scrollbar
            self.scrollY.Hide()
        else:
            self.scrollY.Show()

        self.Layout()
        self.imagepanel.Refresh()

#    def GetClientSize(self):
#        return self.imagepanel.Get
#        pass

    def GetScrollPixelsPerUnit(self):
        return (1,1)

    def Scroll(self, x, y):
        self.scrollX.SetThumbPosition(x)
        self.scrollY.SetThumbPosition(y)
        self.imagepanel.Refresh()

    def OnScrollX(self,event):
        self.xOff = event.GetPosition()

        self.imagepanel.Refresh()

    def OnScrollY(self,event):
        self.yOff = event.GetPosition()
        print self.yOff

        self.imagepanel.Refresh()

    def OnSize(self, event):
        self.Layout()
        self.RefreshScrollbars()
        event.Skip()

    def Scroll(self, dx, dy):
        self.xOff += dx
        self.yOff += dy

        self.RefreshScrollbars()


    

   


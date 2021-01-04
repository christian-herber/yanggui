# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later
 
import wx

from .yanggui import MainFrame

def main(): 
    app = wx.App()
    MainFrame().Show()
    app.MainLoop()

if __name__ == '__main__':
    main()

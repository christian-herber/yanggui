# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later
 
import json
import os.path

import wx
import wx.adv
import wx.html2
import yangson

from .dsrepo import DataStoreRepo
from .errorlog import ErrorLog
from .dataeditor import YangPropertyGrid
from .graphviewer import GraphViewer

class MainFrame(wx.Frame):
    def __init__(self, southboundIf, title, icon):
        wx.Frame.__init__(self, None, title=title)
        
        if icon != None:
            ic = wx.Icon(name=icon, type=wx.BITMAP_TYPE_ICO)
            self.SetIcon(ic)
        
        self.Bind(wx.EVT_CLOSE, self._OnClose)
        self.graphViewer = None
        self.southboundIf = southboundIf
        self.splitter = wx.SplitterWindow(self, -1)
        self.splitter.SetMinimumPaneSize(20)
        self.dataEditorPanel = wx.Panel(self.splitter, -1)
        self.utilsPanel = wx.Panel(self.splitter, -1)
        self.splitter.SplitHorizontally(self.dataEditorPanel, self.utilsPanel)
        self.splitter.SetSashGravity(1.0)
        
        self.utilsBook = wx.Notebook(self.utilsPanel)
        self.errorLogPanel = wx.Panel(self.utilsBook, -1)
        self.utilsBook.AddPage(self.errorLogPanel, 'YANG Data Error Log')
        self.errorLog = ErrorLog(self.errorLogPanel)
        
        self.utilsSizer = wx.BoxSizer()
        self.utilsPanel.SetSizerAndFit(self.utilsSizer)
        self.utilsSizer.Add(self.utilsBook, 1, wx.EXPAND)
        
        self.dataEditor = None
        
        self._InitUI()

        self.config = wx.FileConfig(appName="YANG GUI", localFilename='.config', globalFilename=".config")
        self.config.EnableAutoSave()

        self.includes = list()
        self.dm = None
        self.inst = None
        
        self._LoadConfig()
        
        self.Layout()

    def _OnClose(self, e):
        del self.config
        e.Skip()

    def _InitUI(self):
        self.Maximize()
        self.SetMenuBar(self.YangMenuBar(self))

    class YangMenuBar(wx.MenuBar):
        def __init__(self, parent):
            self.parent = parent
            super().__init__()
            
            self.menuLookup = {
                '&File': {
                    'menu' : wx.Menu(),
                    'items': {
                        'Quit': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_QUIT),
                            'helpString': 'Quit application',
                            'handler': self.parent._OnQuit
                        }
                    }
                },
                '&YANG': {
                    'menu' : wx.Menu(),
                    'items': {
                        'Load Includes...': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
                            'helpString': 'Load YANG include paths',
                            'handler': self.parent._OnLoadIncludes
                        },
                        'Load Library...': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
                            'helpString': 'Load YANG Library',
                            'handler': self.parent._OnLoadLibrary
                        },
                        'View Data Diff': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FIND),
                            'helpString': 'View diff of YANG instance data',
                            'handler': self.parent._OnDiffData
                        },
                        'Save Data': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE),
                            'helpString': 'Save YANG instance data',
                            'handler': self.parent._OnSaveData
                        },
                        'Load Data...': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
                            'helpString': 'Load YANG instance data',
                            'handler': self.parent._OnLoadData
                        }
                    }
                },
                '&Help': {
                    'menu' : wx.Menu(),
                    'items': {
                        '&About': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_HELP),
                            'helpString': 'About',
                            'handler': self.parent._OnAboutBox
                        }
                    }
                }
            }
            
            self._ModifyMenuLookup()
            self._SetupMenus()
            
        def _ModifyMenuLookup(self):
            pass  # can be implemente by inheriting classes
            
        def _SetupMenus(self):
            for title in self.menuLookup:
                menu = self.menuLookup[title]['menu']
                self.Append(menu, title)
                for item in self.menuLookup[title]['items']:
                    opts = self.menuLookup[title]['items'][item]
                    menuItem = menu.Append(wx.ID_ANY, item=item, helpString=opts['helpString'])
                    menuItem.SetBitmap(opts['bmp'])
                    menu.Bind(wx.EVT_MENU, opts['handler'], menuItem)

    def _LoadConfig(self):
        includeFile = self.config.Read("YANG Includes")
        if os.path.isfile(includeFile):
            self._LoadIncludes(includeFile)
            libraryFile = self.config.Read("YANG Library")
            if os.path.isfile(libraryFile):
                self._LoadLibrary(libraryFile)
                if self.dm != None:
                    dataFile = self.config.Read("YANG Data Instance")
                    self._LoadData(dataFile)

    def _LoadIncludes(self, includeFile):
        with open(includeFile, 'r') as f:
            self.includes = json.load(f)
            print('Loaded Includes from {}'.format(includeFile))
            f.close()
        root = os.path.dirname(includeFile)
        self.includes = [os.path.abspath('{}/{}'.format(root, include)) for include in self.includes] 

    def _LoadLibrary(self, libraryFile):
        try:
            self.dm = yangson.DataModel.from_file(libraryFile, self.includes)
            self.config.Write("YANG Library", libraryFile)
        except yangson.exceptions.YangsonException as e:
            self.dm = None
            print("Error while loading the YANG library. Exception: {} - {}".format(str(e), type(e)))
        else:
            print('Loaded Yang Library from {}'.format(libraryFile))
            self.dsrepo = DataStoreRepo(self.dm)
            if self.graphViewer == None:
                self.graphViewer = GraphViewer(self.utilsBook, self.dsrepo, self.southboundIf)
                self.utilsBook.AddPage(self.graphViewer, 'YANG Data Graphs')
            else:
                self.graphViewer.reset()
            self._CreateDataEditor()
            self.dsrepo.load_raw({}) # Load empty data first, can be overwritten later through menu
            self.errorLog.SetDataStore(self.dsrepo)
            
    def _LoadData(self, dataFile):
        try:
            self.dsrepo.load(dataFile)
        except:
            print("Failed to load data from {}".format(dataFile))
            self.dsrepo.load_raw({})

    def _OnDiffData(self, e):
        diff = self.dsrepo.diff()

        dv = DiffViewer()
        dv.browser.SetPage(diff, 'diff')
        dv.Show()

    def _CreateDataEditor(self):
        if self.dataEditor != None:
            self.dataEditorPanel.DestroyChildren()
        env = {
            'dsrepo': self.dsrepo,
            'southboundIf': self.southboundIf,
            'graphViewer': self.graphViewer
        }
        self.dataEditor = YangPropertyGrid(self.dm.schema, self.dataEditorPanel, env)
        self.graphViewer.set_editor(self.dataEditor)

    def _OnQuit(self, e):
        self.Close()

    def _OnLoadData(self, e):
        frame = wx.Frame(None, -1, 'Import YANG instance data')
        openFileDialog = wx.FileDialog(frame, "Open", "", "", "YANG data files (*.json)|*.json", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        openFileDialog.ShowModal()
        self._LoadData(openFileDialog.GetPath())
        self.config.Write("YANG Data Instance", openFileDialog.GetPath())
        openFileDialog.Destroy()
        frame.Destroy()

    def _OnSaveData(self, e):
        dataFile = self.config.Read("YANG Data Instance")
        self.dsrepo.save(dataFile)

    def _OnLoadIncludes(self, e):
        frame = wx.Frame(None, -1, 'Import include paths')
        openFileDialog = wx.FileDialog(frame, "Open", "", "", "Include paths files (*.json)|*.json", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        openFileDialog.ShowModal()
        self._LoadIncludes(openFileDialog.GetPath())
        self.config.Write("YANG Includes", openFileDialog.GetPath())
        openFileDialog.Destroy()
        frame.Destroy()

    def _OnLoadLibrary(self, e):
        frame = wx.Frame(None, -1, 'Open YANG Library')
        openFileDialog = wx.FileDialog(frame, "Open", "", "", "YANG Library files (*.json)|*.json", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        openFileDialog.ShowModal()
        self._LoadLibrary(openFileDialog.GetPath())
        openFileDialog.Destroy()
        frame.Destroy()

    def _OnAboutBox(self, e):
        description = """YANG GUI for editing viewing YANG data models and viewing and modifying YANG data"""

        info = wx.adv.AboutDialogInfo()

        info.SetName('YANG GUI')
        info.SetVersion('0.0')
        info.SetDescription(description)
        info.SetCopyright('(C) 2020-2021 Christian Herber')
        info.AddDeveloper('Christian Herber')
        info.AddDocWriter('Christian Herber')

        wx.adv.AboutBox(info)

class DiffViewer(wx.Frame): 
  def __init__(self):
    wx.Frame.__init__(self, None, title='Diff Viewer')
    sizer = wx.BoxSizer(wx.VERTICAL) 
    self.browser = wx.html2.WebView.New(self) 
    sizer.Add(self.browser, 1, wx.EXPAND, 10) 
    self.SetSizer(sizer) 
    self.SetSize((700, 700)) 
    
def main(southboundIf=None, title="YANG GUI", icon=None): 
    app = wx.App()
    MainFrame(southboundIf, title, icon).Show()
    app.MainLoop()
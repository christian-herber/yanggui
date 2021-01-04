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
from .dataeditor import SchemaTreeNodeCtrl

class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="YANG GUI")

        self.splitter = wx.SplitterWindow(self, -1)
        self.splitter.SetMinimumPaneSize(20)
        self.dataEditorPanel = wx.Panel(self.splitter, -1)
        self.errorLogPanel = wx.Panel(self.splitter, -1)
        self.splitter.SplitHorizontally(self.dataEditorPanel, self.errorLogPanel)
        self.splitter.SetSashPosition(-1)
        self.splitter.SetSashGravity(1.0)
        
        self.dataEditor = None
        self.errorLog = ErrorLog(self.errorLogPanel)
        
        self._InitUI()

        self.config = wx.FileConfig(appName="YANG GUI", localFilename='.config', style=wx.CONFIG_USE_LOCAL_FILE)
        self.config.EnableAutoSave()

        self.includes = list()
        self.dm = None
        self.inst = None

        self._LoadConfig()        

    def _InitUI(self):
        self.Maximize()

        #self._InitToolBar()
        self.SetMenuBar(self.YangMenuBar(self))

    def _InitToolBar(self):
        toolbar = self.CreateToolBar(style=wx.TB_VERTICAL)
        tool = toolbar.AddTool(wx.ID_ANY, 'DataStore', wx.ArtProvider.GetBitmap(wx.ART_HARDDISK))
        tool = toolbar.AddTool(wx.ID_ANY, 'Configuration', wx.ArtProvider.GetBitmap(wx.ART_REPORT_VIEW))
        toolbar.Realize()

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
                        'Load Library...': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
                            'helpString': 'Load YANG Library',
                            'handler': self.parent._OnLoadLibrary
                        },
                        'Load Includes...': {
                            'bmp': wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
                            'helpString': 'Load YANG include paths',
                            'handler': self.parent._OnLoadIncludes
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
        except:
            self.dm = None
            print("Error while loading the YANG library")
        else:
            print('Loaded Yang Library from {}'.format(libraryFile))
            self.dsrepo = DataStoreRepo(self.dm)
            self._CreateDataEditor()
            self.errorLog.SetDataStore(self.dsrepo)

    def _LoadData(self, dataFile):
        try:
            self.dsrepo.load(dataFile)
        except:
            print("Failed to load data from {}".format(dataFile))
            self.dsrepo.load_raw({})
        finally:
            self.dataEditor.SetInstData(self.dsrepo.get_resource())

    def _OnDiffData(self, e):
        diff = self.dsrepo.diff()

        dv = DiffViewer()
        dv.browser.SetPage(diff, 'diff')
        dv.Show()

    def _CreateDataEditor(self):
        self.Freeze()
        if self.dataEditor != None:
            self.dataEditorPanel.DestroyChildren()
        self.dataEditor = SchemaTreeNodeCtrl(self.dataEditorPanel, None, self.dm.schema, self.dsrepo)
        self.Thaw()

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
        self.config.Write("YANG Library", openFileDialog.GetPath())
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
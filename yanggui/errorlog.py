# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import wx

from yangson.exceptions import *

class ErrorLog(wx.ListCtrl):
    def __init__(self, parent):
        super().__init__(parent, id=wx.ID_ANY, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SORT_DESCENDING, size=wx.Size(200, -1))
        self.EnableAlternateRowColours()
        self.dsrepo = None
        self.columns = ['path', 'type', 'tag', 'message']
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(parent, label='YANG Instance Data Errors')
        self.sizer.Add(st)
        self.sizer.Add(self, 1, wx.EXPAND)
        parent.SetSizerAndFit(self.sizer)
        for col, heading in enumerate(self.columns):
            self.AppendColumn(heading=heading)

    def SetDataStore(self, dsrepo):
        self.dsrepo = dsrepo
        if dsrepo != None:
            self.dsrepo.register_error_log_cb(self.NotifyErrorLogChange)

    def NotifyErrorLogChange(self):
        n_errors = len(self.dsrepo.errorLog)
        self.SetItemCount(n_errors)
        if n_errors > 0:
            for col in range(0, len(self.columns)):
                self.SetColumnWidth(col, wx.LIST_AUTOSIZE)

    def OnGetItemText(self, item, column):
        val = ''
        if self.dsrepo != None:
            if item < len(self.dsrepo.errorLog):
                log = self.dsrepo.errorLog[item]
                if self.columns[column] == 'type':
                    if isinstance(log, SemanticError):
                        val = 'Semantic Error'
                    elif isinstance(log, SchemaError):
                        val = 'Schema Error'
                    elif isinstance(log, YangTypeError):
                        val = 'YANG Type Error'
                    else:
                        val = 'Unkown Error'
                elif self.columns[column] == 'path':
                    val = log.instance.json_pointer()
                elif self.columns[column] == 'tag':
                    val = str(log.tag)
                elif self.columns[column] == 'message':
                    val = str(log.message)
                else:
                    pass

        return val
        
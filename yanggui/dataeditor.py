# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import rstr
import wx
import wx.lib.scrolledpanel
import yangson

class SchemaNodeEntry:
    def __init__(self, panel, nodeParent, schemaNode, dsrepo):
        self.ds = 'default'
        self.dsrepo = dsrepo
        self.nodeParent = nodeParent
        self.panel = panel
        self.schemaNode = schemaNode
        self.path = ()
        self.nodeButtons = None

        self._InitCtrl() # To be implemented by inheriting classes

    def NotifyChildValueChange(self, path):
        if self.nodeParent != None:
            self.nodeParent.NotifyChildValueChange(self.path)

    def RefreshInstData(self):
        self.panel.Freeze()
        data = self.dsrepo.get_resource(self.path)
        self.Show(data != None)
        self.SetInstData(data)
        self.panel.Thaw()

    def SetInstData(self, data):
        self.path = None
        if data != None:
            self.path = data.path
        self._DisplayInstData(data)
        if self.nodeButtons != None:
            self.nodeButtons.UpdateButtonState(data)

    def _FormatDescription(self, descr):
        lines = descr.split('\n')

        if len(lines) > 1:
            leadingSpaces = list()
            for line in lines:
                indent = len(line) - len(line.lstrip())
                leadingSpaces.append(indent)

            strip = min(leadingSpaces[1:])
            
            cleanedDesc = list()
            cleanedDesc.append(lines[0])

            for line in lines[1:]:
                cleanedDesc.append(line[strip:])
            descr = '\n'.join(cleanedDesc)

        return descr

    class NodeButtons(wx.BoxSizer):
        def __init__(self, parent):
            super().__init__(wx.HORIZONTAL)
            self.buttonSize = wx.Size(20, 20)
            self.parent = parent
            self.panel = self.parent.panel
            self.buttons = {
                'CreateDelete': {
                    'toggle': True,
                    'bitmap': {
                        False: wx.ArtProvider.GetBitmap(wx.ART_PLUS),
                        True: wx.ArtProvider.GetBitmap(wx.ART_MINUS)
                    },
                    'tooltip': {
                        False: "Create node",
                        True: "Delete node"
                    },
                    'cb': self.parent._OnCreateDelete
                }
            }
            self.buttons = self._AddButtons(self.buttons)
        
        def UpdateButtonState(self, data):
            if 'CreateDelete' in self.buttons:
                btn = self.buttons['CreateDelete']['obj']
                btn.Value = (data != None)
                btn.SetToolTip(self.buttons['CreateDelete']['tooltip'][data != None])
                if self.parent.schemaNode.mandatory:
                    btn.Show(data == None)

        def _AddButtons(self, buttons):
            for name in buttons:
                button = buttons[name]
                if button['toggle']:
                    btn = wx.BitmapToggleButton(self.panel, label=button['bitmap'][False], name=name, size=self.buttonSize)
                    btn.SetBitmapPressed(button['bitmap'][True])
                    btn.Bind(wx.EVT_TOGGLEBUTTON, button['cb'])
                    btn.SetToolTip(button['tooltip'][False])
                else:
                    btn = wx.BitmapButton(self.panel, bitmap=button['bitmap'], name=name, size=self.buttonSize)
                    btn.Bind(wx.EVT_BUTTON, button['cb'])
                    btn.SetToolTip(button['tooltip'])
                buttons[name]['obj'] = btn
                self.Add(btn)
            return buttons

    def _CreateNodeLabel(self, node):
        label = 'rw ' if node.config == True else 'ro '
        label += node.iname()
        if node.mandatory == False:
            label += '?'
        return label
    
    def _OnCreateDelete(self, e):
        btn = self.nodeButtons.buttons['CreateDelete']['obj']
        if btn.Value:
            updated = self._OnCreate(e)
        else:
            updated = self._OnDelete(e)
        self.dsrepo.commit(updated)
        self.RefreshInstData()
        self.nodeParent.NotifyChildValueChange(self.path)

    def _OnCreate(self, e):
        d = self.dsrepo.get_resource(self.nodeParent.path)
        obj = self.GetNewObject()
        name = next(iter(obj))
        self.path = d.path + (name,)
        return d.put_member(name=name, value=obj[name]).top()

    def _OnDelete(self, e):
        d = self.dsrepo.get_resource(self.path)
        return d.up().delete_item(d.name).top()

class InternalNodeCtrl(SchemaNodeEntry):
    def __init__(self, panel, nodeParent, schemaNode, dsrepo):
        self.nodeChildren = dict()
        SchemaNodeEntry.__init__(self, panel, nodeParent, schemaNode, dsrepo)

    def GetNewObject(self, iname=True):
        value = dict()
        for child in self.nodeChildren:
            node = self.nodeChildren[child]
            if node != None:
                if node.schemaNode.mandatory:
                    value.update(node.GetNewObject())
        if iname:
            value = {self.schemaNode.iname(): yangson.instvalue.ObjectValue(val=value)}

        return value

    def Show(self, show=True):
        if hasattr(self, 'propGrid'):
            self.sizer.Show(self.propGrid, show=show, recursive=False)
        if hasattr(self, 'book'):
            self.book.Show(show)
        self.panel.Layout()

    def _DisplayInstData(self, data):
        if data != None:
            for child in self.nodeChildren:
                if self.nodeChildren[child] != None:
                    if isinstance(self.nodeChildren[child].schemaNode, yangson.schemanode.DataNode):
                        if child in data:
                            self.nodeChildren[child].Show()
                            self.nodeChildren[child].SetInstData(data[child])
                        else:
                            self.nodeChildren[child].Show(False)
                            self.nodeChildren[child].SetInstData(None)
                    else:
                        self.nodeChildren[child].SetInstData(data)

    def _ProcessNodeChildren(self, children, bookType='Notebook'):
        grid = wx.FlexGridSizer(cols=2, vgap=1, hgap=10)
        if bookType == 'Choicebook':
            book = wx.Choicebook(self.panel)
        else:
            book = wx.Notebook(self.panel)

        self._AddChildrenToWindow(children, grid, book)

        if grid.IsEmpty():
            del grid
        else:
            self.sizer.Add(grid)
            self.propGrid = grid
        
        if book.PageCount > 0:
            self.sizer.Add(book, 1, wx.EXPAND)
            self.book = book
        else:
            del book

    def _CreateInternalNodeCtrls(self, book, node, scroll):
        if scroll:
            p = wx.lib.scrolledpanel.ScrolledPanel(book)
            p.SetupScrolling(scroll_x=False, scroll_y=scroll, rate_y=20, scrollIntoView=False)
        else:
            p = wx.Panel(book)
        if isinstance(node, yangson.schemanode.ContainerNode):
            obj = ContainerNodeCtrl(p, self, node, self.dsrepo)
        elif isinstance(node, yangson.schemanode.SequenceNode):
            if isinstance(node, yangson.schemanode.LeafListNode):
                obj = LeafListNodeCtrl(p, self, node, self.dsrepo)
            elif isinstance(node, yangson.schemanode.ListNode):
                obj = ListNodeCtrl(p, self, node, self.dsrepo)
        elif isinstance(node, yangson.schemanode.ChoiceNode):
            obj = ChoiceNodeCtrl(p, self, node, self.dsrepo)
        elif isinstance(node, yangson.schemanode.CaseNode):
            obj = CaseNodeCtrl(p, self, node, self.dsrepo)
        else:
            print("unknown node {}, type: {}".format(node, type(node)))
            obj = None
        book.AddPage(p, self._CreateNodeLabel(node))
        return obj

    def _CreateLeafNodeCtrls(self, grid, node):
        label = self._CreateNodeLabel(node)
        grid.Add(wx.StaticText(self.panel, label=label))
        obj = LeafNodeCtrl(self.panel, self, node, self.dsrepo)
        grid.Add(obj.sizer)
        return obj

    def _AddChildrenToWindow(self, children, grid, nb):
        children = sorted(children, key=lambda x: x.config, reverse=True)
        for child in children:
            if isinstance(child, yangson.schemanode.GroupNode):
                if isinstance(child, yangson.schemanode.RpcActionNode):
                    pass # TODO: Hanndling for RPCs and actions
                else:
                    self._AddChildrenToWindow(child.children, grid, nb)
            else:
                if isinstance(child, yangson.schemanode.LeafNode):
                    self.nodeChildren[child.iname()] = self._CreateLeafNodeCtrls(grid, child)
                else:
                    self.nodeChildren[child.iname()] = self._CreateInternalNodeCtrls(nb, child, False)

class SchemaTreeNodeCtrl(InternalNodeCtrl):
    def _InitCtrl(self):
        self.panel.Freeze()
        self._ProcessSchemaTreeNode(self.schemaNode)
        self.panel.Thaw()

    def _ProcessSchemaTreeNode(self, schemaNode):
        # This is the root of the Yang Models(s)
        self.nodeChildren = dict()
        subnbs = dict()
        namespaces = list()
        for child in schemaNode.children:
            namespaces.append(child.ns)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(sizer)
        nb = wx.Notebook(self.panel)

        children = sorted(schemaNode.children, key=lambda x: x.ns + x.name)

        for child in children:
            if child.ns not in subnbs:
                if (namespaces.count(child.ns) > 1):
                    # Multiple nodes exist within the namespace
                    # Create another notebook
                    tab = wx.Panel(nb)
                    nb.AddPage(tab, child.ns)
                    subnbs[child.ns] = wx.Notebook(tab)
                    subsizer = wx.BoxSizer()
                    subsizer.Add(subnbs[child.ns], 1, wx.EXPAND)
                    tab.SetSizerAndFit(subsizer)
            if (namespaces.count(child.ns) > 1):
                parentNb = subnbs[child.ns]
            else:
                parentNb = nb
            self.nodeChildren[child.iname()] = self._CreateInternalNodeCtrls(parentNb, child, True)
        sizer.Add(nb, 1, wx.EXPAND)

class ChoiceNodeCtrl(InternalNodeCtrl):
    def _InitCtrl(self):
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizerAndFit(self.sizer)
        self._ProcessNodeChildren(self.schemaNode.children, bookType='Choicebook')

    def GetNewObject(self):
        iname = list(self.nodeChildren.keys())[0]
        if self.schemaNode.default_case != None:
            iname = self.schemaNode.default_case[0]
        obj = self.nodeChildren[iname].GetNewObject()
        return obj

class CaseNodeCtrl(InternalNodeCtrl):
    def _InitCtrl(self):
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizerAndFit(self.sizer)
        self._ProcessNodeChildren(self.schemaNode.children)

    def GetNewObject(self):
        obj = InternalNodeCtrl.GetNewObject(self)
        name = next(iter(obj))
        return obj[name]

class ContainerNodeCtrl(InternalNodeCtrl):
    def _InitCtrl(self):
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizerAndFit(self.sizer)
        self.nodeButtons = self.NodeButtons(self)
        self.sizer.Add(self.nodeButtons)
        self._ProcessNodeChildren(self.schemaNode.children)

class SequenceNodeCtrl(SchemaNodeEntry):
    def _InitCtrl(self):
        self.nodeButtons = self.ListNodeButtons(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizerAndFit(self.sizer)
        self.sizer.Add(self.nodeButtons)
        self._InitTable()
        self.EnableAlternateRowColours()
        self.columns = list()
        self.columnMinWidth = list()
        self._ProcessNode()
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self._OnSelectEvent, self)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._OnSelectEvent, self)

    class ListNodeButtons(SchemaNodeEntry.NodeButtons):
        def __init__(self, parent):
            SchemaNodeEntry.NodeButtons.__init__(self, parent)
            self.listButtons = {
                'InsertBefore': {
                    'toggle': False,
                    'bitmap': wx.ArtProvider.GetBitmap(wx.ART_GO_UP),
                    'cb': self.parent._OnInsertBefore,
                    'tooltip': 'Insert new list entry before currently selected entry'
                },
                'InsertAfter': {
                    'toggle': False,
                    'bitmap': wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN),
                    'cb': self.parent._OnInsertAfter,
                    'tooltip': 'Insert new list entry after currently selected entry'
                },
                'DeleteSelected': {
                    'toggle': False,
                    'bitmap': wx.ArtProvider.GetBitmap(wx.ART_CROSS_MARK),
                    'cb': self.parent._OnDeleteSelected,
                    'tooltip': 'Delete all selected list entries'
                }
            }
            self.listButtons = self._AddButtons(self.listButtons)
            self.buttons.update(self.listButtons)
            
        def UpdateButtonState(self, data):
            super().UpdateButtonState(data)
            firstSel = self.parent.GetFirstSelected()
            itemCount = 0 if data == None else len(data.value)
            self.buttons['DeleteSelected']['obj'].Show(firstSel >= 0)
            self.buttons['InsertAfter']['obj'].Show(data != None)
            self.buttons['InsertBefore']['obj'].Show(data != None)

    class EntryCtrl(InternalNodeCtrl):
        def _InitCtrl(self):
            self.sizer = self.nodeParent.sizer
            self._ProcessNodeChildren(self.schemaNode.children)

        def GetNewObject(self):
            obj = InternalNodeCtrl.GetNewObject(self)
            name = next(iter(obj))
            return obj[name]

    def Show(self, show=True):
        wx.ListCtrl.Show(self, show)

    def OnGetItemText(self, item, column):
        value = ''
        path = self.path + (item,)
        d = self.dsrepo.get_resource(path)
        if d != None:
            if len(self.columns) == 1:
                value = str(d)
            elif self.columns[column] in d:
                obj = d[self.columns[column]]
                if isinstance(obj.schema_node, yangson.schemanode.LeafNode):
                    value = str(obj)  # TODO use cannonical string
                elif isinstance(obj.schema_node, yangson.schemanode.SequenceNode):
                    value = str((len(obj.value)))
                else:
                    value = 'present'
        return value

    def GetNewObject(self):
        return {self.schemaNode.iname(): yangson.instvalue.ArrayValue(val=[self.nodeChild.GetNewObject()])}

    def NotifyChildValueChange(self, path):
        self.RefreshItem(path[-1])
        self._RearrangeColumns()
        
    def _RearrangeColumns(self):
        self.Freeze()
        for col in range(0, len(self.columns)):
            self.SetColumnWidth(col, wx.LIST_AUTOSIZE)
            if self.GetColumnWidth(col) < self.columnMinWidth[col]:
                self.SetColumnWidth(col, self.columnMinWidth[col])                
        self.Thaw()

    def _ProcessNode(self):
        self.columns = self._AddChildrenToTable(self.children)
        self.nodeChild = self.EntryCtrl(self.panel, self, self.schemaNode, self.dsrepo)

    def _OnInsertAfter(self, e):
        self._OnInsert(e, False)

    def _OnInsertBefore(self, e):
        self._OnInsert(e)

    def _OnInsert(self, e, before=True):       
        if self.ItemCount > 0:
            item = self.GetFirstSelected()
            if not before:
                item = item + self.GetSelectedItemCount() - 1
                if item < 0:
                    item = self.ItemCount - 1
            else:
                if item < 0:
                    item = 0        
            d = self.dsrepo.get_resource(self.path)[item]
            value = self.nodeChild.GetNewObject()
            if before:
                updated = d.insert_before(value=value).top()
            else:
                updated = d.insert_after(value=value).top()
        else:
            updated = self._OnCreate(e)
        self.dsrepo.commit(updated)
        self.RefreshInstData()

    def _OnDeleteSelected(self, e):
        item = self.GetFirstSelected()
        remove = list()
        updatedValue = self.dsrepo.get_resource(self.path)
        while item >= 0:
            remove.append(item)
            item = self.GetNextSelected(item)
        for item in sorted(remove, reverse=True):
            updatedValue = updatedValue.delete_item(item)
        self.dsrepo.commit(updatedValue.top())
        self.RefreshInstData()

    def _DisplayInstData(self, data):
        if data != None:
            self.SetItemCount(len(data.value))
            self.nodeChild.Show()
            idx = self.GetFirstSelected()
            if idx >= 0:            
                self.nodeChild.SetInstData(data[idx])
            else:
                self.nodeChild.Show(False)
            self.RefreshItems(0, len(data.value))
        else:
            self.SetItemCount(0)
            self.nodeChild.Show(False)
        
        self._RearrangeColumns()

    def _AddChildrenToTable(self, children):
        columns = list()
        for child in children:
            if isinstance(child, yangson.schemanode.GroupNode):
                columns.append(self._AddChildrenToTable(child))
            else:
                columns.append(child.iname())
        for heading in columns:
            self.AppendColumn(heading=heading)
        for col in range(0, len(columns)):          
            self.SetColumnWidth(col, wx.LIST_AUTOSIZE_USEHEADER)
            self.columnMinWidth.append(self.GetColumnWidth(col))
        return columns

    def _OnSelectEvent(self, e):
        idx = self.GetFirstSelected()
        d = self.dsrepo.get_resource(self.path)
        self.panel.Freeze()
        self.SetInstData(d)
        self.panel.Thaw()
    
class ListNodeCtrl(SequenceNodeCtrl, wx.ListCtrl):
    def _InitTable(self):
        wx.ListCtrl.__init__(self, self.panel, style=wx.LC_REPORT | wx.LC_VIRTUAL, size=wx.Size(200, -1))
        self.sizer.Add(self, 0, wx.EXPAND)
        self.children = self.schemaNode.data_children()

class LeafListNodeCtrl(SequenceNodeCtrl, wx.ListCtrl):
    def _InitTable(self):
        wx.ListCtrl.__init__(self, self.panel, style=wx.LC_REPORT | wx.LC_VIRTUAL)
        self.sizer.Add(self)
        self.children = [self.schemaNode]

    class EntryCtrl(SequenceNodeCtrl.EntryCtrl):
        def _InitCtrl(self):
            self.sizer = self.nodeParent.sizer
            self.ctrl = LeafNodeCtrl(self.panel, self, self.schemaNode, self.dsrepo)
            self.sizer.Add(self.ctrl.sizer)

        def Show(self, show=True):
            self.ctrl.Show(show)
            
        def GetNewObject(self):
            obj = self.ctrl.GetNewObject()
            name = next(iter(obj))
            return obj[name]

        def _DisplayInstData(self, data):
            if data != None:
                self.ctrl.SetInstData(data)

class LeafNodeCtrl(SchemaNodeEntry):
    def _InitCtrl(self):
        self.ctrl = None
        self.sizer = wx.BoxSizer()
        self.leafLookup = [
            (yangson.datatype.EnumerationType, self.EnumerationNodeCtrl),
            (yangson.datatype.IdentityrefType, self.IdentityrefNodeCtrl),
            (yangson.datatype.BooleanType, self.BooleanNodeCtrl),
            (yangson.datatype.BitsType, self.BitsNodeCtrl),
            (yangson.datatype.BinaryType, self.BinaryNodeCtrl),
            (yangson.datatype.StringType, self.StringNodeCtrl),
            (yangson.datatype.IntegralType, self.IntegralNodeCtrl),
            (yangson.datatype.Decimal64Type, self.Decimal64NodeCtrl),
            (yangson.datatype.EmptyType, self.EmptyNodeCtrl),
            (yangson.datatype.InstanceIdentifierType, self.InstanceIdentifierNodeCtrl)
        ]

        if isinstance(self.schemaNode.type, yangson.datatype.UnionType):
            nodeType = self.schemaNode.type.types[0]
        elif isinstance(self.schemaNode.type, yangson.datatype.LeafrefType):
            nodeType = self.schemaNode.type.ref_type
        else:
            nodeType = self.schemaNode.type
        for leaf in self.leafLookup:
            if isinstance(nodeType, leaf[0]):
                self.ctrl = leaf[1](self, self.panel, nodeType)
                break
        if self.ctrl == None:
            print('Unknown leaf node: {}'.format(nodeType))
        
        if self.schemaNode.description != None:
            descr = self._FormatDescription(self.schemaNode.description)
            self.ctrl.SetToolTip(descr)

        if isinstance(self.schemaNode, yangson.schemanode.LeafNode):
            self.nodeButtons = self.NodeButtons(self)
            self.sizer.Add(self.nodeButtons)
        self.sizer.Add(self.ctrl)

    def GetNewObject(self):
        return {self.schemaNode.iname(): self.ctrl.GetNewObject()}

    def Show(self, show=True):
        pass
        self.ctrl.Show(show)

    def _DisplayInstData(self, data):
        if data != None:
            self.ctrl._DisplayInstData(data)

    def _OnValue(self, e):
        d = self.dsrepo.get_resource(self.path)
        updated = d.update(self.ctrl.InstData())
        try:
            updated.validate()
            if self.ctrl.IsModified():
                self.ctrl.SetBackgroundColour("pale green")
        except:
            self.ctrl.SetBackgroundColour("pink")
        self.ctrl.Refresh()
        e.Skip()

    def _OnValueUpdate(self, e):
        d = self.dsrepo.get_resource(self.path)
        instData = self.ctrl.InstData()
        updated = d.update(instData)
        try:
            updated.validate()
        except:
            self.RefreshInstData()
        else:
            self.dsrepo.commit(updated.top())
            self.RefreshInstData()
            self.nodeParent.NotifyChildValueChange(self.path)
        self.ctrl.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        self.ctrl.Refresh()

    class LeafNodeWidget:
        def __init__(self, parent, panel, sntype):
            self.panel = panel
            self.type = sntype
            self.parent = parent
            self._InitCtrl()

        def _DisplayInstData(self, data):
            value = self.InstDataToValue(data)
            if "SetValue" in dir(self):
                self.SetValue(value)
            else:
                print('No method for displaying data in leaf node available ({})'.format(self.type))

        def InstData(self):
            return self.type.parse_value(self.Value)

        def InstDataToValue(self, data):
            return self.type.canonical_string(data.value)

        def GetNewObject(self):
            val = self.type.parse_value(self.GetNewValue())
            return val

        def GetNewValue(self):
            return '-'

    class BitsNodeCtrl(LeafNodeWidget, wx.CheckListBox):
        def _InitCtrl(self):
            choices = list(self.type.bit.keys())
            wx.CheckListBox.__init__(self, self.panel, choices=choices, size=wx.Size(200, -1))
            self.Bind(wx.EVT_CHECKLISTBOX, self.parent._OnValueUpdate)

        def InstData(self):
            return self.CheckedStrings

        def _DisplayInstData(self, data):
            self.SetCheckedStrings(list(data.value))

        def GetNewObject(self):
            return () ## empty tuple means no bits are set

    class BooleanNodeCtrl(LeafNodeWidget, wx.CheckBox):
        def _InitCtrl(self):
            wx.CheckBox.__init__(self, self.panel)
            self.Bind(wx.EVT_CHECKBOX, self.parent._OnValueUpdate)

        def InstData(self):
            return self.Value
        
        def InstDataToValue(self, data):
            return data.value
        
        def GetNewObject(self):
            return False

    class Decimal64NodeCtrl(LeafNodeWidget, wx.TextCtrl):
        def _InitCtrl(self):
            wx.TextCtrl.__init__(self, self.panel, style=wx.TE_PROCESS_ENTER)
            self.Bind(wx.EVT_TEXT_ENTER, self.parent._OnValueUpdate)
            self.Bind(wx.EVT_TEXT, self.parent._OnValue)
        
        def GetNewValue(self):
            return '0.0'

    class BinaryNodeCtrl(LeafNodeWidget, wx.TextCtrl):
        def _InitCtrl(self):
            wx.TextCtrl.__init__(self, self.panel, style=wx.TE_PROCESS_ENTER)
            self.minLength = 0
            if hasattr(self.type, 'length'):
                if isinstance(self.type.length, yangson.constraint.Intervals):
                    interval = self.type.length.intervals[0]
                    if len(interval) == 2:
                        self.minLength = interval[0]
                        self.maxLength = interval[1]
                        self.SetMaxLength(self.maxLength)
                    else:
                        self.minLength = interval[0]
            self.Bind(wx.EVT_TEXT_ENTER, self.parent._OnValueUpdate)
            self.Bind(wx.EVT_TEXT, self.parent._OnValue)
        
        def GetNewObject(self):
            values = [0] * max(self.minLength, 1)
            return bytes(values)

    class StringNodeCtrl(LeafNodeWidget, wx.TextCtrl):
        def _InitCtrl(self):
            wx.TextCtrl.__init__(self, self.panel, style=wx.TE_PROCESS_ENTER)
            self.minLength = 0
            if hasattr(self.type, 'length'):
                if isinstance(self.type.length, yangson.constraint.Intervals):
                    interval = self.type.length.intervals[0]
                    if len(interval) == 2:
                        self.minLength = interval[0]
                        self.maxLength = interval[1]
                        self.SetMaxLength(self.maxLength)
                    else:
                        self.minLength = interval[0]
            self.Bind(wx.EVT_TEXT_ENTER, self.parent._OnValueUpdate)
            self.Bind(wx.EVT_TEXT, self.parent._OnValue)
        
        def GetNewValue(self):
            if hasattr(self.type, 'patterns') and len(self.type.patterns) > 0:
                value = rstr.xeger(self.type.patterns[0].regex)
            else:
                value = rstr.rstr('x', max(self.minLength, 1))
            return value

    class IntegralNodeCtrl(LeafNodeWidget, wx.TextCtrl):
        def _InitCtrl(self):
            wx.TextCtrl.__init__(self, self.panel, style=wx.TE_PROCESS_ENTER)
            self.Bind(wx.EVT_TEXT_ENTER, self.parent._OnValueUpdate)
            self.Bind(wx.EVT_TEXT, self.parent._OnValue)
            self.default = '0'
            if hasattr(self.type, 'range'):
                if isinstance(self.type.range, yangson.constraint.Intervals):
                    self.default = str(self.type.range.intervals[0][0])
            
        def GetNewValue(self):
            return self.default

    class EmptyNodeCtrl(LeafNodeWidget, wx.StaticText):
        def _InitCtrl(self):
            wx.ComboBox.__init__(self, self.panel, label='[null]')

        def _DisplayInstData(self, data):
            pass          

    class EnumerationNodeCtrl(LeafNodeWidget, wx.ComboBox):
        def _InitCtrl(self):
            self.choices = list(self.type.enum.keys())
            wx.ComboBox.__init__(self, self.panel, choices=self.choices, style=wx.CB_READONLY)
            self.Bind(wx.EVT_COMBOBOX, self.parent._OnValueUpdate)

        def GetNewValue(self):
            return self.choices[0]

    class IdentityrefNodeCtrl(LeafNodeWidget, wx.ComboBox):
        def _InitCtrl(self):
            self.choices = list()
            for choice in list(self.type.sctx.schema_data.derived_from_all(self.type.bases)):
                self.choices.append(self.type.canonical_string(choice))
            wx.ComboBox.__init__(self, self.panel, choices=self.choices, style=wx.CB_SORT | wx.CB_READONLY)
            self.Bind(wx.EVT_COMBOBOX, self.parent._OnValueUpdate)

        def GetNewObject(self):
            value = list(self.type.sctx.schema_data.derived_from_all(self.type.bases))[0]
            return value

    class InstanceIdentifierNodeCtrl(LeafNodeWidget, wx.TextCtrl):
        def _InitCtrl(self):
            wx.TextCtrl.__init__(self, self.panel, style=wx.TE_PROCESS_ENTER)
            self.Bind(wx.EVT_TEXT_ENTER, self.parent._OnValueUpdate)
            self.Bind(wx.EVT_TEXT, self.parent._OnValue)
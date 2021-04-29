# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import rstr
import json
import wx
import wx.lib.scrolledpanel
import wx.propgrid as wxpg
import yangson

from pubsub import pub

def _AppendNodeToPath(path, iname):
    l = list(path)
    l.append(iname)
    return tuple(l)

def _CreateNodeLabel(node):
    # Create labels insipred by https://tools.ietf.org/html/rfc8340
    label = 'rw ' if node.config == True else 'ro '
    label += node.iname()
    if isinstance(node, yangson.schemanode.LeafNode):
        if not node.mandatory:
            label += '?'
        if node.units != None:
            label += ' [{}]'.format(node.units)
    if isinstance(node, yangson.schemanode.ContainerNode) and node.presence:
        label += '!'
    if isinstance(node, yangson.schemanode.SequenceNode):
        label += '*'
        if isinstance(node, yangson.schemanode.ListNode):
            keys = list()
            for key in node.keys:
                keys.append(key[0])
            label += ' [{}]'.format(', '.join(keys))         
            
    return label

def _FormatDescription(descr):
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
    
class YangPropertyGrid(wxpg.PropertyGridManager):
    __registered = False
    
    def __init__(self, sn, parent, env, id=wx.ID_ANY):
        self.parent = parent
        self.schemaNode = sn
        self.env = env
        size = wx.Size(-1, -1)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.parent.SetSizer(sizer)

        self.parent.Freeze()
        super().__init__(parent, id=id, name=sn.iname(), size=size, style=wxpg.PG_NO_INTERNAL_BORDER)
        self.ExtraStyle |= wxpg.PG_EX_HELP_AS_TOOLTIPS

        if YangPropertyGrid.__registered == False:
            self.RegisterEditor(self.YangTextCtrlEditor())
            self.RegisterEditor(self.YangListEditor())
            self.RegisterEditor(self.YangLeafListEditor())
            self.RegisterEditor(self.YangBitsEditor())
            self.RegisterEditor(self.YangChoiceEditor())
            self.RegisterEditor(self.YangSpinCtrlEditor())
            YangPropertyGrid.__registered = True

        self.path = tuple()
        self.choices = list()

        self.children = sorted(self.schemaNode.children, key=lambda x: x.iname())
        for child in self.children:
            page = self.AddPage(label=child.iname(), pageObj=self.Page(child, self, self.env))
            page.FitColumns()
            self.choices.append(child.iname())

        self.cb = wx.ComboBox(self.parent, choices=self.choices, style=wx.CB_READONLY, value=self.choices[0])
        self.cb.Bind(wx.EVT_COMBOBOX, self.OnCBSelect)
        sizer.Add(self.cb)
        sizer.Add(self, -1, wx.EXPAND)
        
        self.parent.Layout()
        self.parent.Thaw()
        
    def OnCBSelect(self, e):
        self.SelectPage(e.GetString())

    class Page(wxpg.PropertyGridPage):
        def __init__(self, sn, parent, env):
            self.schemaNode = sn
            self.parent = parent
            self.env = env
            self.path = tuple()
            super().__init__()
            phantomProperty = wxpg.StringProperty(label="Data node", name=sn.iname() + 'heading', value='Value')
            self.Append(phantomProperty) # FIXME: Without this, buttons for the first YANG property do not show
            self.SetPropertyReadOnly(phantomProperty, set=True, flags=wxpg.PG_DONT_RECURSE)
            prop = YangPropertyGrid._CreateChildProperty(self, sn)
            if prop != None:
                self.Append(prop)

    def SetInstDataPath(self, path):
        self.path = path
        self._SetChildrenInstDataPath(path)

    def Enable(self, enable=True):
        if self.schemaNode.parent != None:
            for prop in self.Properties:
                prop.Enable(enable)

    def _SetChildrenInstDataPath(self, path):
        for prop in self.Properties:
            child_path = _AppendNodeToPath(path, prop.schemaNode.iname())
            prop.SetInstDataPath(child_path)

    def GetNewObject(self, iname=True):
        value = dict()
        for prop in self.Properties:
            if prop.schemaNode.mandatory:
                val = prop.GetNewObject(iname=True)
                value.update(val)
        if iname:
            return {self.schemaNode.iname(): yangson.instvalue.ObjectValue(val=value)}
        else:
            return yangson.instvalue.ObjectValue(val=value)

    def AddLeafProperties(self, leaf):
        leafLookup = [
            (yangson.datatype.EnumerationType, YangPropertyGrid.YangEnumerationProperty),
            (yangson.datatype.IdentityrefType, YangPropertyGrid.YangIdentityrefProperty),
            (yangson.datatype.BooleanType, YangPropertyGrid.YangBooleanProperty),
            (yangson.datatype.BitsType, YangPropertyGrid.YangBitsProperty),
            (yangson.datatype.BinaryType, YangPropertyGrid.YangBinaryProperty),
            (yangson.datatype.StringType, YangPropertyGrid.YangStringProperty),
            (yangson.datatype.IntegralType, YangPropertyGrid.YangIntegralProperty),
            (yangson.datatype.Decimal64Type, YangPropertyGrid.YangDecimal64Property),
            (yangson.datatype.EmptyType, YangPropertyGrid.YangEmptyProperty),
            (yangson.datatype.InstanceIdentifierType, YangPropertyGrid.YangGenericProperty)
        ]

        if isinstance(leaf.type, yangson.datatype.UnionType):
            nodeType = leaf.type.types[0]
        elif isinstance(leaf.type, yangson.datatype.LeafrefType):
            nodeType = leaf.type.ref_type
        else:
            nodeType = leaf.type
        for propClass in leafLookup:
            if isinstance(nodeType, propClass[0]):
                prop = propClass[1](self, leaf, nodeType)
                break
        if prop == None:
            print('Unknown leaf node: {}'.format(nodeType))

        return prop

    def _AddChildrenToParentProperty(self, children):
        for child in children:
            prop = YangPropertyGrid._CreateChildProperty(self, child)
            if prop != None:
                self.AddPrivateChild(prop)

    def _CreateChildProperty(self, child):
        prop = None
        if isinstance(child, yangson.schemanode.TerminalNode):
            if isinstance(child, yangson.schemanode.LeafNode):
                prop = YangPropertyGrid.AddLeafProperties(self, child)
            elif isinstance(child, yangson.schemanode.LeafListNode):
                prop = YangPropertyGrid.YangLeafListProperty(self, child)
        elif isinstance(child, yangson.schemanode.ContainerNode):
            prop = YangPropertyGrid.YangContainerProperty(self, child)
        elif isinstance(child, yangson.schemanode.ListNode):
            prop = YangPropertyGrid.YangListProperty(self, child)
        return prop

    class YangEditor:
        CREATE   = wx.ID_HIGHEST + 12
        DELETE   = wx.ID_HIGHEST + 13
        PUT      = wx.ID_HIGHEST + 14
        GET      = wx.ID_HIGHEST + 15
        ADVANCED = wx.ID_HIGHEST + 16

        _tooltips = {
            CREATE: 'Create data node',
            DELETE: 'Delete data node',
            PUT: 'Perform PUT operation for this data node',
            GET: 'Perform GET operation for this data node',
            ADVANCED: 'Show advanced options for this data node'
        }

        def __init__(self):
            pass

        def GetName(self):
            return self.__class__.__name__

        def CreateControls(self, propGrid, property, pos, sz):
            buttons = wxpg.PGMultiButton(propGrid, sz)
            dataValid = (property.env['dsrepo'].get_resource(property.path) != None)
            self._AddCustomButtons(buttons, dataValid)
            if dataValid:
                if not property.schemaNode.mandatory:
                    buttons.AddBitmapButton(wx.ArtProvider.GetBitmap(wx.ART_MINUS), id=self.DELETE)
            else:
                buttons.AddBitmapButton(wx.ArtProvider.GetBitmap(wx.ART_PLUS), id=self.CREATE)
                
            if (property.env['southboundIf'] != None) and (property.env['southboundIf'].resources != None):
                if property.schemaNode.data_path() in property.env['southboundIf'].resources:
                    if not property.schemaNode.config and dataValid:
                        buttons.AddButton("P", id=self.PUT)
                    buttons.AddButton("G", id=self.GET)
            if dataValid:
                buttons.AddButton("ADV", id=self.ADVANCED)
            wndList = super().CreateControls(
                                    propGrid,
                                    property,
                                    pos,
                                    buttons.GetPrimarySize())
            buttons.Finalize(propGrid, pos)
            self.buttons = buttons
            for i in range(self.buttons.Count):
                id = self.buttons.GetButtonId(i)
                if id in self._tooltips:
                    b = self.buttons.GetButton(i)
                    b.SetToolTip(self._tooltips[id])

            return wxpg.PGWindowList(wndList.GetPrimary(), buttons)

        def _AddCustomButtons(self, buttons, dataValid):
            pass

        class AdvancedMenu(wx.Menu):
            def __init__(self, prop):
                self.prop = prop
                super().__init__()
                self.items = {
                    'GET_LOOP': {
                        'kind': wx.ITEM_CHECK,
                        'create': False,
                        'tooltip': 'GET data instance from target in a cyclic loop',
                        'cb': self._OnGetLoop
                    },
                    'ADD_TO_GRAPH': {
                        'kind': wx.ITEM_CHECK,
                        'create': False,
                        'tooltip': 'Add to graph',
                        'cb': self._OnAddToGraph
                    }
                }
                if isinstance(prop.schemaNode, yangson.schemanode.LeafNode) and isinstance(prop.schemaNode.type, yangson.datatype.NumericType):
                    self.items['ADD_TO_GRAPH']['create'] = True
                if (prop.env['southboundIf'] != None) and (prop.env['southboundIf'].resources != None):
                    if prop.schemaNode.data_path() in prop.env['southboundIf'].resources:
                        if not prop.schemaNode.config:
                            self.items['GET_LOOP']['create'] = True

                self._AddItems()
                self._ShowAdvancedOptions()

            def _AddItems(self):
                for name in self.items:
                    item = self.items[name]
                    if item['create']:
                        if item['kind'] == wx.ITEM_CHECK:
                            i = self.AppendCheckItem(wx.ID_ANY, item=item['tooltip'], help=item['tooltip'])
                        else:
                            i = self.Append(wx.ID_ANY, item=item['tooltip'], helpString=item['tooltip'], kind=item['kind'])
                        self.Bind(wx.EVT_MENU, item['cb'], i)
                        self.items[name]['obj'] = i

            def _ShowAdvancedOptions(self):
                if 'obj' in self.items['ADD_TO_GRAPH']:
                    is_in_graph = self.prop.env['graphViewer'].is_in_graph(self.prop.topic)
                    self.items['ADD_TO_GRAPH']['obj'].Check(is_in_graph)
                if 'obj' in self.items['GET_LOOP']:
                    is_in_loop = self.prop.env['graphViewer'].is_in_loop(self.prop.topic)
                    self.items['GET_LOOP']['obj'].Check(is_in_loop)
                panel = self.prop.GetGrid().GetPanel()
                panel.PopupMenu(self)
            
            def _OnGetLoop(self, e):
                i = e.EventObject.items['GET_LOOP']
                if i['obj'].IsChecked():
                    self.prop.env['graphViewer'].add(self.prop.path, self.prop.topic, loop=True, plot=False)
                else:
                    self.prop.env['graphViewer'].remove_from_data_loop(self.prop.topic)

            def _OnAddToGraph(self, e):
                i = e.EventObject.items['ADD_TO_GRAPH']
                if i['obj'].IsChecked():
                    self.prop.env['graphViewer'].add(self.prop.path, self.prop.topic)
                else:
                    self.prop.env['graphViewer'].remove(self.prop.topic)

        def OnEvent(self, propGrid, aProperty, ctrl, event):
            if event.GetEventType() == wx.wxEVT_BUTTON:
                evtId = event.GetId()
                if evtId == self.CREATE:
                    aProperty.Create()
                    aProperty.RecreateEditor()
                elif evtId == self.DELETE:
                    aProperty.Delete()
                    aProperty.RecreateEditor()
                elif evtId == self.PUT:
                    self.Put(aProperty)
                elif evtId == self.GET:
                    self.Get(aProperty)
                elif evtId == self.ADVANCED:
                    self.AdvancedMenu(aProperty)
                return False
            else:
                return super().OnEvent(propGrid, aProperty, ctrl, event)

        def Put(self, prop):
            data = prop.env['dsrepo'].get_resource(prop.path)
            if prop.env['southboundIf'] != None:
                prop.env['southboundIf'].put(prop.env['dsrepo'].dm, data, prop.path)

        def Get(self, prop):
            if prop.env['southboundIf'] != None:
                data = prop.env['dsrepo'].get_resource(prop.path)
                data = prop.env['southboundIf'].get(prop.env['dsrepo'].dm, data, prop.path)
                if data != None:
                    prop.env['dsrepo'].commit(data.top())
                
    class YangChoiceEditor(YangEditor, wxpg.PGChoiceEditor):
        def __init__(self):
            wxpg.PGChoiceEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

    class YangSpinCtrlEditor(YangEditor, wxpg.PGSpinCtrlEditor):
        def __init__(self):
            wxpg.PGSpinCtrlEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

    class YangTextCtrlEditor(YangEditor, wxpg.PGTextCtrlEditor):
        def __init__(self):
            wxpg.PGTextCtrlEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

    class YangListEditor(YangEditor, wxpg.PGTextCtrlEditor):
        LISTEDIT = wx.ID_HIGHEST + 20
        def __init__(self):
            wxpg.PGTextCtrlEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

        def _AddCustomButtons(self, buttons, dataValid):
            if dataValid:
                self._tooltips[self.LISTEDIT] = 'Launch viewer for this list'
                buttons.Add("...", id=self.LISTEDIT)

        def OnEvent(self, propGrid, aProperty, ctrl, event):
            if (event.GetEventType() == wx.wxEVT_BUTTON) and (event.GetId() == self.LISTEDIT):
                lv = YangListViewer(aProperty)
                lv.Show()
                return False
            return super().OnEvent(propGrid, aProperty, ctrl, event)

    class YangBitsEditor(YangEditor, wxpg.PGTextCtrlEditor):
        BITSEDIT = wx.ID_HIGHEST + 22
        def __init__(self):
            wxpg.PGTextCtrlEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

        def _AddCustomButtons(self, buttons, dataValid):
            if dataValid:
                self._tooltips[self.BITSEDIT] = 'Launch editor dialog for bits data node'
                buttons.Add("...", id=self.BITSEDIT)
            
        class YangBitsDialog(wx.Dialog):
            def __init__(self, property):
                self.prop = property
                super().__init__(None, title=property.schemaNode.iname())
                sizer = wx.BoxSizer(wx.VERTICAL)

                data = self.prop.env['dsrepo'].get_resource(self.prop.path)
                
                choices = list(self.prop.type.bit.keys())
                self.lb = lb = wx.CheckListBox(self, choices=choices)
                lb.SetCheckedStrings(list(data.value))
                sizer.Add(lb)
                btns = self.CreateStdDialogButtonSizer(0)

                ok = wx.Button(self, wx.ID_OK, 'OK')
                cncl = wx.Button(self, wx.ID_CANCEL, 'Cancel')
                ok.Bind(wx.EVT_BUTTON, self.OnDialog)
                
                btns.Add(ok)
                btns.Add(cncl)

                sizer.Add(btns)
                self.SetSizer(sizer)
                sizer.Fit(self)

            def OnDialog(self, event):
                data = self.lb.CheckedStrings
                d = self.prop.env['dsrepo'].get_resource(self.prop.path)
                updated = d.update(data).top()
                self.prop.env['dsrepo'].commit(updated)
                event.Skip()

        def OnEvent(self, propGrid, aProperty, ctrl, event):
            if (event.GetEventType() == wx.wxEVT_BUTTON) and (event.GetId() == self.BITSEDIT):
                d = self.YangBitsDialog(aProperty)
                d.ShowModal()
                d.Destroy()
                return False
            return super().OnEvent(propGrid, aProperty, ctrl, event)

    class YangLeafListEditor(YangEditor, wxpg.PGTextCtrlEditor):
        LEAFLISTEDIT = wx.ID_HIGHEST + 21
        def __init__(self):
            wxpg.PGTextCtrlEditor.__init__(self)
            YangPropertyGrid.YangEditor.__init__(self)

        def _AddCustomButtons(self, buttons, dataValid):
            if dataValid:
                self._tooltips[self.LEAFLISTEDIT] = 'Launch editor dialog for this leaf list'
                buttons.Add("...", id=self.LEAFLISTEDIT)
            
        class YangLeafListDialog(wx.Dialog):
            def __init__(self, property):
                self.prop = property
                super().__init__(None, title=property.schemaNode.iname())
                sizer = wx.BoxSizer(wx.VERTICAL)

                data = self.prop.env['dsrepo'].get_resource(self.prop.path)
                self.lb = lb = wx.adv.EditableListBox(self)
                strings = list()
                for value in data.value:
                    str = self.prop.type.canonical_string(value)
                    strings.append(str)
                lb.SetStrings(strings)
                sizer.Add(lb)

                btns = self.CreateStdDialogButtonSizer(0)

                ok = wx.Button(self, wx.ID_OK, 'OK')
                cncl = wx.Button(self, wx.ID_CANCEL, 'Cancel')
                ok.Bind(wx.EVT_BUTTON, self.OnDialog)
                
                btns.Add(ok)
                btns.Add(cncl)

                sizer.Add(btns)
                self.SetSizer(sizer)
                sizer.Fit(self)

            def OnDialog(self, event):
                strings = self.lb.GetStrings()
                values = list()
                for string in strings:
                    values.append(self.prop.type.parse_value(string))
                d = self.prop.env['dsrepo'].get_resource(self.prop.path)
                updated = d.update(yangson.instvalue.ArrayValue(val=values)).top()
                self.prop.env['dsrepo'].commit(updated)
                event.Skip()

        def OnEvent(self, propGrid, aProperty, ctrl, event):
            if (event.GetEventType() == wx.wxEVT_BUTTON) and (event.GetId() == self.LEAFLISTEDIT):
                d = self.YangLeafListDialog(aProperty)
                d.ShowModal()
                d.Destroy()
                return False
            return super().OnEvent(propGrid, aProperty, ctrl, event)

    class YangPropertyBase:
        def __init__(self, parent, sn, sntype):
            self.type = sntype
            self.parent = parent
            if self.parent == None:
                self.parent = self.GetGrid()
            self.schemaNode = sn
            self.env = parent.env
            if self.schemaNode.description != None:
                descr = _FormatDescription(self.schemaNode.description)
                self.SetHelpString(descr)
            self.dataValid = False
            self.SetInitialPath()

        def SetNameAndLabel(self, sn):
            self.name = sn.data_path()
            self.label = _CreateNodeLabel(sn)

        def Delete(self, path=None):
            if path == None:
                path = self.path
            d = self.env['dsrepo'].get_resource(path)
            if d != None:
                updated = d.up().delete_item(d.name).top()
                self.env['dsrepo'].commit(updated)

        def Create(self, path=None):
            if path == None:
                path = self.path
            
            d = self.env['dsrepo'].get_resource(self.parent.path)
            if d == None:
                self.parent.Create()
                d = self.env['dsrepo'].get_resource(self.parent.path)
            obj = self.GetNewObject(iname=False)
            name = self.schemaNode.iname()
            updated = d.put_member(name=name, value=obj).top()
            self.env['dsrepo'].commit(updated)
            
        def ValidateValue(self, value, validationInfo):
            d = self.env['dsrepo'].get_resource(self.path)
            try:
                data = self._ParseInstDataFromValue(value)
            except:
                validationInfo.FailureMessage = 'Data entered is syntactically incorrect for the given data type and cannot be parsed'
                return False
            if data is None:  # data should deleted
                if self.schemaNode.mandatory:
                    validationInfo.FailureMessage = 'Data of mandatory node cannot be deleted'
                    return False
                if d != None: # data did not exist anyway
                    updated = d.up().delete_item(d.name)
                else:
                    return True
            else:
                if d == None: # data should be created
                    p = self.env['dsrepo'].get_resource(self.parent.path)
                    updated = p.put_member(name=self.schemaNode.iname(), value=data)
                else:
                    updated = d.update(data)
                try:
                    updated.validate()
                except:
                    m = self._GetFailureMessage()
                    if m != None:
                        validationInfo.FailureMessage = m
                    return False

            self.env['dsrepo'].commit(updated.top())
            return True

        def _GetFailureMessage(self):
            return 'Validation of data resulted in error ({}): {}'.format(self.type.error_tag, self.type.error_message)

        def UpdateData(self, data, path):
            self.SetInstDataPath(path)
            self.DisplayYangInstData(data)
            self.UpdateChildren(data, path)
            
        def UpdateChildren(self, data, path):
            pass

        def DisplayYangInstData(self, data):
            if data != None:
                self.dataValid = True
                newValue = self._ConvertInstDataToValue(data)
                if newValue != self.GetValue():
                    self.SetValue(newValue)
                    self.GetGrid().Expand(self)
            else:
                self.GetGrid().Collapse(self)
                if self.dataValid:
                    self.SetValueToUnspecified()
                self.dataValid = False
            self.dataValid = (data != None)

        def SetInitialPath(self):
            iname = self.schemaNode.iname()
            self.path = _AppendNodeToPath(self.parent.path, iname)
            self.SubscribeTopic()

        def SetInstDataPath(self, path):
            if path != self.path:
                self.path = path
                self.SubscribeTopic(unsubfirst=True)

        def SubscribeTopic(self, path=None, unsubfirst=False):
            if unsubfirst:
                pub.unsubscribe(self.DataCallback, self.topic)
            if path == None:
                path = self.path
            self.topic = self.env['dsrepo'].path_to_topic(path, self.schemaNode)
            pub.subscribe(self.DataCallback, self.topic)

        def DataCallback(self, data):
            self.DisplayYangInstData(data)

        def _ParseInstDataFromValue(self, value):
            return self.type.parse_value(value)

        def _ConvertInstDataToValue(self, data):
            return self.type.canonical_string(data.value)

        def GetNewObject(self, iname=True):
            data = self.GetDefaultData()
            obj = self.ConvertDataToObject(data)
            if iname:
                return {self.schemaNode.iname(): obj}
            else:
                return obj

        def GetDefaultData(self):
            return self._ParseInstDataFromValue(self.GetDefaultValue())
            
        def ConvertDataToObject(self, data):
            return data

    class YangGenericProperty(wxpg.StringProperty, YangPropertyBase):
        def __init__(self, parent, sn, sntype):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            super().__init__(self.label, self.name)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, sntype)
            self.SetEditor("YangTextCtrlEditor")
            self.SetValueToUnspecified()

    class YangEmptyProperty(YangGenericProperty):
        def __init__(self, parent, sn, sntype):
            super().__init__(parent, sn, sntype)

        def GetDefaultValue(self):
            return ""

    class YangLinearProperty(YangGenericProperty):
        def __init__(self, parent, sn, sntype):
            super().__init__(parent, sn, sntype)
            self.minLength = 0
            if hasattr(self.type, 'length'):
                if isinstance(self.type.length, yangson.constraint.Intervals):
                    interval = self.type.length.intervals[0]
                    if len(interval) == 2:
                        self.minLength = interval[0]
                        self.maxLength = interval[1]
                    else:
                        self.minLength = interval[0]

    class YangBinaryProperty(YangLinearProperty):
        def GetNewObject(self, iname=True):
            val = bytes([0] * max(self.minLength, 1))
            if iname:
                return {self.schemaNode.iname(): val}
            else:
                return val
        
    class YangStringProperty(YangLinearProperty):
        def GetDefaultData(self):
            if hasattr(self.type, 'patterns') and len(self.type.patterns) > 0:
                data = rstr.xeger(self.type.patterns[0].regex)
            else:
                data = rstr.rstr('x', self.minLength)
            return data
        
        def _ParseInstDataFromValue(self, value):
            if value == "":
                data = None
            elif value[0] != "\"":
                data = None
            else:
                data = value = value.split('\"')[1]
            return data

        def _ConvertInstDataToValue(self, data):
            value = super()._ConvertInstDataToValue(data)
            value = '\"{}\"'.format(value)
            return value

    class YangIntegralProperty(YangGenericProperty):
        def __init__(self, parent, sn, sntype):
            super().__init__(parent, sn, sntype)
            self.default = 0
            if hasattr(self.type, 'range'):
                if isinstance(self.type.range, yangson.constraint.Intervals):
                    self.default = self.type.range.intervals[0][0]

        def GetDefaultData(self):
            return self.default
        
    class YangChoiceProperty(wxpg.EnumProperty, YangPropertyBase):
        def __init__(self, parent, sn, sntype):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            self.choices = self.GetChoices(sntype)
            super().__init__(self.label, self.name, self.choices)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, sntype)
            self.SetEditor("YangChoiceEditor")

        def _ParseInstDataFromValue(self, value):
            if value == 0:
                return None
            else:
                return super()._ParseInstDataFromValue(self.choices[value])

        def GetDefaultValue(self):
            return 1

    class YangEnumerationProperty(YangChoiceProperty):
        def GetChoices(self, sntype):
            return [''] + list(sntype.enum.keys())

    class YangIdentityrefProperty(YangChoiceProperty):
        def GetChoices(self, sntype):
            choices = ['']
            for choice in list(sntype.sctx.schema_data.derived_from_all(sntype.bases)):
                choices.append(sntype.canonical_string(choice))
            return choices

    class YangBooleanProperty(wxpg.BoolProperty, YangPropertyBase):
        def __init__(self, parent, sn, sntype):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            super().__init__(label=self.label, name=self.name)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, sntype)
            self.SetEditor("YangChoiceEditor")
            self.SetValueToUnspecified()

        def GetDefaultData(self):
            return False

        def _ParseInstDataFromValue(self, value):
            return value

        def _ConvertInstDataToValue(self, data):
            return data.value

    class YangBitsProperty(wxpg.StringProperty, YangPropertyBase):
        def __init__(self, parent, sn, sntype):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            super().__init__(label=self.label, name=self.name)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, sntype)
            self.SetEditor("YangBitsEditor")

        def GetDefaultData(self):
            return ()

        def _ConvertInstDataToValue(self, data):
            return json.dumps(data.value)

    class YangDecimal64Property(YangGenericProperty):
        def GetDefaultData(self):
            return 0.0

    class YangInternalProperty(wxpg.StringProperty, YangPropertyBase):
        def __init__(self, parent, sn):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            super().__init__(label=self.label, name=self.name)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, None)
            self._SetEditor()
            YangPropertyGrid._AddChildrenToParentProperty(self, self.schemaNode.data_children())
            self.SetValueToUnspecified()
        
        def ConvertDataToObject(self, data):
            return yangson.instvalue.ObjectValue(val=data)
            
        def UpdateChildren(self, data, path):
            # TODO: do not update children if data is None and was None before
            items = self.GetChildCount()
            for i in range(items):
                prop = self.Item(i)
                childPath = _AppendNodeToPath(path, prop.schemaNode.iname())
                childData = None
                if data != None:
                    if prop.schemaNode.iname() in data:
                        childData = data[prop.schemaNode.iname()]
                prop.UpdateData(childData, childPath)

        def _SetEditor(self):
            self.SetEditor("YangTextCtrlEditor")

        def GetDefaultData(self):
            value = dict()
            items = self.GetChildCount()
            for i in range(items):
                prop = self.Item(i)
                if prop.schemaNode.mandatory and not isinstance(prop.schemaNode.parent, yangson.schemanode.CaseNode):
                    val = prop.GetNewObject(iname=True)
                    value.update(val)
            return value

    class YangContainerProperty(YangInternalProperty, YangPropertyBase):
        def ValidateValue(self, value, validationInfo):
            return True
        
        def _ConvertInstDataToValue(self, data):
            value = str(data.value)
            if len(value) > 100:
                value = value[0:100].rsplit(',', 1)[0] + ' ...}'
            return value

    class YangLeafListProperty(wxpg.StringProperty, YangPropertyBase):
        def __init__(self, parent, sn):
            YangPropertyGrid.YangPropertyBase.SetNameAndLabel(self, sn)
            super().__init__(label=self.label, name=self.name)
            YangPropertyGrid.YangPropertyBase.__init__(self, parent, sn, sn.type)
            self.SetEditor("YangLeafListEditor")
            self.SetValueToUnspecified()

        def _GetFailureMessage(self):
            return 'Leaf List contents incorrect.'

        def GetDefaultData(self):
            return []
        
        def ConvertDataToObject(self, data):
            return yangson.instvalue.ArrayValue(val=data)

        def _ParseInstDataFromValue(self, value):
            if value == '':
                return None
            return yangson.instvalue.ArrayValue(json.loads(value))

        def _ConvertInstDataToValue(self, data):
            return json.dumps(data.value)

    class YangListProperty(YangInternalProperty):
        def __init__(self, parent, sn):
            self.index = 0
            super().__init__(parent, sn)

        def _SetEditor(self):
            self.SetEditor("YangListEditor")

        def Delete(self):
            super().Delete(path=self.listPath)
            self.index = 0
            self.SetInstDataPath(self.listPath)

        def Create(self):
            self.index = 0
            super().Create(path=self.listPath)
            self.RefreshInstData()

        def Select(self, index):
            self.index = index
            self.RefreshInstData()

        def RefreshInstData(self):
            data = self.env['dsrepo'].get_resource(self.listPath)
            self.UpdateData(data, self.listPath)
            
        def UpdateChildren(self, data, path):
            entryData = None
            if data != None:
                entryData = data[self.index]
            entryPath = path + (self.index, )
            super().UpdateChildren(entryData, entryPath)
            
        def DataCallback(self, data):
            self.DisplayYangEntryInstData(data)

        def DisplayYangEntryInstData(self, data):
            super().DisplayYangInstData(data)
            
        def DisplayYangInstData(self, data):
            entryData = None
            if data != None:
                entryData = data[self.index]
            self.DisplayYangEntryInstData(entryData)

        def SetEntryInstDataPath(self, path):
            super().SetInstDataPath(path)

        def SetInstDataPath(self, path):
            if path != self.listPath: # different table selected
                self.index = 0
            self.listPath = path
            self.SetEntryInstDataPath(path + (self.index, ))

        def GetNewEntryObject(self):
            data = super().GetDefaultData()
            obj = super().ConvertDataToObject(data)
            return obj

        def GetDefaultData(self):
            return [self.GetNewEntryObject()]
        
        def ConvertDataToObject(self, data):
            return yangson.instvalue.ArrayValue(val=data)
        
        def ValidateValue(self, value, validationInfo):
            path = self.path[0:-1] + (int(value), )
            d = self.env['dsrepo'].get_resource(path)
            if d != None:
                self.Select(int(value))
            else:
                validationInfo.FailureMessage = 'List index out of bounds.'
                return False
            return True
        
        def _ConvertInstDataToValue(self, data):
            return self.index # just return the currently selected index to be displayed

        def SetInitialPath(self):
            iname = self.schemaNode.iname()
            self.listPath = _AppendNodeToPath(self.parent.path, iname)
            self.path = _AppendNodeToPath(self.listPath, self.index)
            self.SubscribeTopic()

class YangListViewer(wx.Frame):
    def __init__(self, aProperty):
        self.property = aProperty
        self.nodeParent = aProperty.parent
        self.schemaNode = aProperty.schemaNode
        self.env = aProperty.env
        self.path = aProperty.listPath
        self.topic = self.env['dsrepo'].path_to_topic(self.path, self.schemaNode)
        super().__init__(None, title='/'.join(list(map(str, self.path))))
        self.panel = wx.Panel(self)
        self._InitCtrl()
        pub.subscribe(self.DisplayYangInstData, self.topic)      
        self.Bind(wx.EVT_CLOSE, self._OnCloseEvent, self)

    def _OnCloseEvent(self, e):
        pub.unsubscribe(self.DisplayYangInstData, self.topic)
        e.Skip()        

    class YangListCtrl(wx.ListCtrl):
        def __init__(self, parent):
            self.parent = parent
            super().__init__(parent.panel, style=wx.LC_REPORT | wx.LC_VIRTUAL, size=wx.Size(200, -1))
            self.EnableAlternateRowColours()
            self.columnMinWidth = list()
            self.columns = self._AddChildrenToTable(self.parent.schemaNode.data_children())
            self.Bind(wx.EVT_LIST_ITEM_SELECTED, self._OnSelectEvent, self)
            self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._OnSelectEvent, self)

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

        def RearrangeColumns(self):
            self.Freeze()
            for col in range(0, len(self.columns)):
                self.SetColumnWidth(col, wx.LIST_AUTOSIZE)
                if self.GetColumnWidth(col) < self.columnMinWidth[col]:
                    self.SetColumnWidth(col, self.columnMinWidth[col])
            self.Thaw()

        def OnGetItemText(self, item, column):
            value = ''
            path = self.parent.path + (item,)
            d = self.parent.env['dsrepo'].get_resource(path)
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

        def _OnSelectEvent(self, e):
            idx = self.GetFirstSelected()
            p = self.parent
            p.nodeButtons.buttons['DeleteSelected']['obj'].Enable(idx >= 0)
            if p.property.listPath == p.path:  # current table is visible in propgrid
                if idx >= 0:
                    p.property.Select(idx)

    def _InitCtrl(self):
        self.nodeButtons = self.Buttons(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.nodeButtons)
        self.list = self.YangListCtrl(self)
        self.sizer.Add(self.list, -1, wx.EXPAND)
        self.RefreshInstData()
        self.panel.SetSizerAndFit(self.sizer)
        self.panel.Layout()

    class Buttons(wx.BoxSizer):
        def __init__(self, parent):
            super().__init__(wx.HORIZONTAL)
            self.buttonSize = wx.Size(20, 20)
            self.parent = parent
            self.panel = self.parent.panel
            self.buttons = {
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
            self.buttons = self._AddButtons(self.buttons)
            self.buttons.update(self.buttons)

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

        def UpdateButtonState(self, data):
            firstSel = self.parent.list.GetFirstSelected()
            self.buttons['DeleteSelected']['obj'].Enable(firstSel >= 0)
            self.buttons['InsertAfter']['obj'].Enable(data != None)
            self.buttons['InsertBefore']['obj'].Enable(data != None)

    def _OnInsertAfter(self, e):
        self._OnInsert(e, False)

    def _OnInsertBefore(self, e):
        self._OnInsert(e)

    def _OnInsert(self, e, before=True):
        if self.list.GetItemCount() > 0:
            item = self.list.GetFirstSelected()
            if not before:
                item = item + self.list.GetSelectedItemCount() - 1
                if item < 0:
                    item = self.list.GetItemCount() - 1
            else:
                if item < 0:
                    item = 0
            d = self.env['dsrepo'].get_resource(self.path + (item, ))
            value = self.property.GetNewEntryObject()
            if before:
                updated = d.insert_before(value=value).top()
            else:
                updated = d.insert_after(value=value).top()
        else:
            updated = self.property.Create()
        self.env['dsrepo'].commit(updated)

    def _OnDeleteSelected(self, e):
        item = self.list.GetFirstSelected()
        remove = list()
        updatedValue = self.env['dsrepo'].get_resource(self.path)
        while item >= 0:
            remove.append(item)
            item = self.list.GetNextSelected(item)
        for item in sorted(remove, reverse=True):
            updatedValue = updatedValue.delete_item(item)
        self.env['dsrepo'].commit(updatedValue.top())

    def RefreshInstData(self):
        data = None
        data = self.env['dsrepo'].get_resource(self.path)
        if data != None:
            items = len(data.value)
        else:
            items = 0
        self.list.SetItemCount(items)
        self.list.RefreshItems(0, items)
        self.list.RearrangeColumns()
        self.nodeButtons.UpdateButtonState(data)
        self.panel.Layout()

    def DisplayYangInstData(self, data):
        self.RefreshInstData()

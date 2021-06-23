# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import json
import yangson
import difflib
from pubsub import pub

class DataStoreRepo:
    def __init__(self, dm):
        self.dm = dm
        self.datastores = dict()
        self.errorLog = list()
        self.error_log_callbacks = list()
   
    def load_raw(self, inst_raw, name='default'):
        datastore = self.dm.from_raw(inst_raw)
        self.datastores[name] = datastore
        self.datastores['load'] = datastore
        self._find_all_errors(datastore)
        self._publish_data(None, self.datastores[name], publish_on_no_data=True)
   
    def load(self, file_name, name='default'):
        with open(file_name, 'r') as f:
            print("Loading YANG Instance Data from {}".format(file_name))
            inst_raw = json.load(f)
            self.load_raw(inst_raw, name)
            f.close()

    def save(self, file_name, name='default'):
        self.datastores['load'] = self.get_resource()
        inst_raw = self.get_resource().raw_value()
        with open(file_name, 'w') as f:
            json.dump(inst_raw, f, indent=4)
            f.close()

    def commit(self, ds, name='default'):
        old_ds = self.datastores[name]
        self.datastores[name] = ds
        self._find_all_errors(self.datastores[name])
        self._publish_data(old_ds, ds)
        
    def path_to_topic(self, path, schema_node):
        topic = '.'.join(list(map(str, path)))
        if topic == '':
            topic = 'yang'
        else:
            topic = 'yang.{}'.format(topic)
        if isinstance(schema_node, yangson.schemanode.SequenceNode):
            topic += '.sequenceNode'
        elif isinstance(schema_node, yangson.schemanode.InternalNode):
            topic += '.internalNode'
        return topic

    def _publish_data(self, old_data, new_data, publish_on_no_data=False):
        publish = False
        new_data_valid = (new_data != None)
        old_data_valid = (old_data != None)

        if new_data_valid:
            valid_data = new_data
            pub_data = new_data
            if old_data_valid:
                if new_data.value != old_data.value:
                    publish = True
                elif isinstance(valid_data.value, yangson.instvalue.StructuredValue):
                    if new_data.value.timestamp != old_data.value.timestamp:
                        publish = True
                elif new_data.timestamp != old_data.timestamp:
                    publish = True
            else:
                publish = True
        elif old_data_valid:
            pub_data = None
            valid_data = old_data
            publish = True

        if publish:
            topic = self.path_to_topic(valid_data.path, valid_data.schema_node)
            pub.sendMessage(topic, data=pub_data)
            if isinstance(valid_data.value, yangson.instvalue.ArrayValue):
                old_len = 0
                new_len = 0
                if old_data_valid:
                    old_len = len(old_data.value)
                if new_data_valid:
                    new_len = len(new_data.value)
                length = max(old_len, new_len)
                for idx in range(length):
                    old_entry = None
                    if idx < old_len:
                        old_entry = old_data[idx]
                    new_entry = None
                    if idx < new_len:
                        new_entry = new_data[idx]
                    self._publish_data(old_entry, new_entry, publish_on_no_data)
            elif isinstance(valid_data.value, yangson.instvalue.StructuredValue):
                keys = list()
                if new_data_valid:
                    keys = list(new_data.value.keys())
                if old_data_valid:
                    keys = keys + list(old_data.value.keys())
                keys = list(set(keys))
                for iname in keys:
                    old_child = None
                    new_child = None
                    if old_data_valid and iname in old_data:
                        old_child = old_data[iname]
                    if new_data_valid and iname in new_data:
                        new_child = new_data[iname]
                    self._publish_data(old_child, new_child, publish_on_no_data)

    def register_error_log_cb(self, callback):
        self.error_log_callbacks.append(callback)
        
    def _find_all_errors(self, node):
        if isinstance(node, yangson.instance.RootNode):
            self.errorLog = list()  # empty the error log
        self._validate_node(node)
        if isinstance(node.value, yangson.instvalue.ObjectValue):
            for item in node.value:
                self._find_all_errors(node[item])
        elif isinstance(node.value, yangson.instvalue.ArrayValue):
            for entry in node:
                self._find_all_errors(entry)
        
        if isinstance(node, yangson.instance.RootNode):
            self._removeDuplicates()
            self.errorLog = list(set(self.errorLog))
            self.errorLog = sorted(self.errorLog , key=lambda log: log.instance.path)
            self._notify_error_log_cbs()
            
    def _removeDuplicates(self):
        errorLogClean = list()
        for error in self.errorLog:
            seen = False
            for errorClean in errorLogClean:
                if str(error) == str(errorClean):
                    seen = True
                    break
            if not seen:
                errorLogClean.append(error)
        self.errorLog = errorLogClean
            
    def _notify_error_log_cbs(self):
        for cb in self.error_log_callbacks:
            cb()

    def _validate_node(self, inst):
        try:
            inst.validate(ctype=yangson.enumerations.ContentType.all)
        except yangson.exceptions.YangsonException as e:
            self._log_error(e)

    def _log_error(self, e):
        self.errorLog.append(e)

    def diff(self, name1='load', name2='default'):
        inst_raw1 = self.get_resource(name=name1).raw_value()
        inst_raw2 = self.get_resource(name=name2).raw_value()
        
        lines1 = json.dumps(inst_raw1, indent=4).split('\n')
        lines2 = json.dumps(inst_raw2, indent=4).split('\n')
        differ = difflib.HtmlDiff()
        diff = differ.make_file(lines1, lines2, context=True)
        return diff
    
    def get_resource(self, path=(), name='default'):
        if not name in self.datastores:
            return None
        d = self.datastores[name]
        for index in path:
            if d == None:
                return None
            if isinstance(d.value, yangson.instvalue.ArrayValue):
                if 0 <= index < len(d.value):
                    d = d[index]
                else:
                    return None
            elif index in d:
                d = d[index]
            else:
                return None
        return d
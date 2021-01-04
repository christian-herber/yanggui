# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import json
import yangson
import difflib

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
        self.datastores[name] = ds
        self._find_all_errors(self.datastores[name])
        
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
            self.errorLog = list(set(self.errorLog)) # remove duplicates
            #self.errorLog.sort(key = lambda obj: obj.path, obj.tag)
            self.errorLog = sorted(self.errorLog , key=lambda log: log.path)
            self._notify_error_log_cbs()
            
    def _notify_error_log_cbs(self):
        for cb in self.error_log_callbacks:
            cb()

    def _validate_node(self, inst):
        try:
            inst.validate(ctype=yangson.enumerations.ContentType.all)
        except yangson.exceptions.YangTypeError as e:
            self._log_error(e)
        except yangson.exceptions.SchemaError as e:
            self._log_error(e)
        except yangson.exceptions.SemanticError as e:
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
        d = self.datastores[name]
        try:
            for index in path:
                d = d[index]
            data = d
        except:
            data = None # resource wasn't found
            
        return data
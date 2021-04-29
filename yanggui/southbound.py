# Copyright 2020-2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import yangson

class SouthBoundIf:
    def __init__(self):
        self.resources = list()
    
    def put(self, dm, data, path):
        pass
        
    def get(self, dm, data, path) -> yangson.instance.InstanceNode: 
        return None
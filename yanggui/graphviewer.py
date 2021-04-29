# Copyright 2021, Christian Herber
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import wx
from wx.lib.plot import PlotCanvas, PlotGraphics, PolyLine
from pubsub import pub

class GraphViewer(wx.Panel):
    def __init__(self, parent, dsrepo, sbif):
        self.reset()
        self.dsrepo = dsrepo
        self.sbif = sbif
        super().__init__(parent, -1)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.canvas = PlotCanvas(self)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        self.SetSizerAndFit(sizer)
        self.canvas.enableLegend = True
        self.Layout()
        
        self.timer = wx.Timer(self)
        self.timer.Start(milliseconds=self.interval)
        self.Bind(wx.EVT_TIMER, self.get_loop)
        
        self.colors = [
            [166,206,227],
            [31,120,180],
            [178,223,138],
            [51,160,44],
            [251,154,153],
            [227,26,28],
            [253,191,111],
            [255,127,0],
            [202,178,214],
            [106,61,154],
            [255,255,153],
            [177,89,40]
        ]

    def reset(self):
        self.datasources = list()
        self.interval = 1000 # in ms
        self.max_samples = 100 # to ensure stability, only plot a maximum of this number of samples
        self.max_age = self.interval * self.max_samples / 1000 # [s] if data points are older than this, drop them
        self.latest_sample = 0

    def set_editor(self, editor):
        self.editor = editor

    def value_change_cb(self, data):
        for plot in self.datasources:
            if plot['path'] == data.path:
                plot['data'].append((data.timestamp.timestamp(), data.value))
                if data.timestamp.timestamp() > self.latest_sample:
                    self.latest_sample = data.timestamp.timestamp()
                break
        self.canvas.Draw(self.draw())
        
    def add(self, path, topic, plot=True, loop=False):
        entry_updated = False
        for d in self.datasources:
            if d['path'] == path:
                if loop:
                    d['loop'] = loop
                if plot:
                    d['plot'] = plot
                entry_updated = True
        if not entry_updated:
            d = {
                'topic': topic,
                'path': path,
                'loop': loop,
                'data': [],
                'line': None,
                'legend': str(path),
                'plot': plot
            }
            self.datasources.append(d)
        if plot:
            pub.subscribe(self.value_change_cb, d['topic'])
            self.canvas.Draw(self.draw())
        
    def remove(self, topic):
        for idx, plot in enumerate(self.datasources):
            if plot['topic'] == topic:
                deleteIdx = idx
        pub.unsubscribe(self.value_change_cb, topic)
        del self.datasources[deleteIdx]

    def draw(self):
        plots = []
        styleIdx = 0
        for plot in self.datasources:
            plot['data'] = [p for p in plot['data'] if p[0] > (self.latest_sample - self.max_age)]
            if plot['plot'] == True:
                color = wx.Colour(self.colors[styleIdx][0], self.colors[styleIdx][1], self.colors[styleIdx][2])
                styleIdx += 1
                plot['line'] = PolyLine(plot['data'], legend=plot['legend'], colour=color, width=3)
                plots.append(plot['line'])
        return PlotGraphics(plots, '', 'time [s]', '')
    
    def is_in_graph(self, topic):
        for d in self.datasources:
            if d['topic'] == topic:
                if d['plot']:
                    return True
                else:
                    break
        return False
    
    def is_in_loop(self, topic):
        for d in self.datasources:
            if d['topic'] == topic:
                if d['loop']:
                    return True
                else:
                    break
        return False
    
    def remove_from_data_loop(self, topic):
        for idx, d in enumerate(self.datasources):
            if d['topic'] == topic:
                self.datasources[idx]['loop'] = False
    
    def get_loop(self, e):
        for d in self.datasources:       
            if d['loop']:
                if self.sbif != None:
                    data = self.dsrepo.get_resource(d['path'])
                    data = self.sbif.get(self.dsrepo.dm, data, d['path'])
                    if data != None:
                        self.dsrepo.commit(data.top())

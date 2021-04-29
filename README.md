# YANG GUI: A Graphical User Interface (GUI) for viewing and editing YANG data (RFC 7950)

Copyright (C) 2020-2021 by Christian Herber

ABOUT
=============

YANG GUI is a python implemented GUI for working with YANG models and their corresponding instance data.
The GUI based on wxPython (https://wxpython.org/), a cross-platform GUI toolkit.

YANG model and data handling is done using Yangson https://yangson.labs.nic.cz/index.html. The GUI was developed using version 1.4.4 of Yangson. The supported features of YANG etc. are naturally a subset of the features supported by Yangson.

The intention of the GUI is to provide easy means of getting on overview over YANG data, YANG models, and allow also inexperienced engineers to work with YANG. 

FEATURES
=============

The GUI supports the following high level features:
- YANG instance data editor
    - Load and display instance data
    - Create or delete nodes in the data tree
    - Enforcement of correct data through specialized controls
    - Store modified data to file
- YANG error log: Error view for entire data tree
- Diff viewer: Side-by-side comparison of intial and modified data
- Graph support: Draw line graphs for values like counters
- Southbound interface integration: Prepared for integration with soutbound interfaces

INSTALLATION
=============

YANG GUI is distributed via PyPI and can be installed using pip

`pip install yanggui`

After successful installation, it should be possible to launch the GUI using

`python -m yanggui`

GETTING STARTED
=============

To get started with YANG GUI, at least two things are needed:
- A list of include directories specifying where YANG modules can be found
- A YANG library data file ([RFC7895](https://tools.ietf.org/html/rfc7895))

The includes should be in place first. They can be loaded through <kbd>YANG | Load Includes...</kbd>. The file containing is expected to be a .json containing an array with the includes paths. For example, this file would load include paths for IEEE 802 and IETF modules:

```json
[
    "./yang/standard/ieee/published/802",
    "./yang/standard/ieee/published/802.1",
    "./yang/standard/ieee/published/802.3",
    "./yang/standard/ietf/RFC",
]
```

With includes in place, a YANG libarary can be loaded through <kbd>YANG | Load Libary...</kbd>. After successfully loading the library, the specified YANG modules are loaded and the editor appears. As no data has been loaded, the editor will only show the top level modules, and nodes can be added by clicking the plus icons.

With the YANG modules loaded through the libarary, data files can be opened following <kbd>YANG | Load Data...</kbd>. After succesfully loading the data, it can be inspected and modified in the editor. Also, any errors will be shown in the Data Errors View at the bottom.
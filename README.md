mecode
======

GCode for all


TODO
====
* split footer.txt into different files.
* upper or lowercase kwargs (decorator?)
* replace "z" with either A, B, C, or D (or anything else)
* add pressure_boxes to `setup()` method
* is set_valve the best name?
* finalize interface on aerotech functions.
* set_home should default to X=0, Y=0
* build out multi-nozzle support
    * include multi-nozzle support in view method.
* check if arc radius is possible (could be too small)
* add 'auto' radius option, which is sets it to half the length
* add default values to docstrings
* factor out aerotech specific methods into their own class

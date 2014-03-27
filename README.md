mecode
======

GCode for all

Mecode is designed to simplify GCode generation. It is not a slicer, and it
can not convert CAD models to 3D printer ready code. It is simply a convenience
layer just above GCode. If you have a project that requires you to write your
own GCode, then mecode is for you.

Installation
------------
```bash
$ git clone https://github.com/jminardi/mecode.git
$ cd mecode
$ python setup.py install
```


TODO
----
* split footer.txt into different files.
* replace "z" with either A, B, C, or D (or anything else)
* add pressure_boxes to `setup()` method
* is set_valve the best name?
* finalize interface on aerotech functions.
* build out multi-nozzle support
    * include multi-nozzle support in view method.
* factor out aerotech specific methods into their own class

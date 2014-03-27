Mecode
======

### GCode for all

Mecode is designed to simplify GCode generation. It is not a slicer, thus it
can not convert CAD models to 3D printer ready code. It simply provides a
convenient, human-readable layer just above GCode. If you often find
yourself manually writing your own GCode, then mecode is for you.

Basic Use
---------
To use, simply instantiate the `G` object and use its methods to trace your
desired tool path.

```python
from mecode import G
g = G()
g.move(10, 10)  # move 10mm in x and 10mm in y
g.arc(x=10, y=5, radius=20, direction='CCW')  # counterclockwise arc with a radius of 5
g.meander(5, 10, spacing=1)  # trace a rectangle meander with 1mm spacing between passes
g.abs_move(x=1, y=1)  # move the tool head to position (1, 1)
g.home()  # move the tool head to the origin (0, 0)
```

By default `mecode` simply prints the generated GCode to stdout. If instead you
want to generate a file, you can pass a filename and turn off the printing when
instantiating the `G` object.

```python
g = G(outfile='path/to/file.gcode', print_lines=False)
```

*NOTE:* `g.teardown()` must be called after all commands are executed if you
are writing to a file.

The resulting toolpath can be visualized in 3D using the `mayavi` package with
the `view()` method:

```python
g = G()
g.meander(10, 10, 1)
g.view()
```

Installation
------------
```bash
$ git clone https://github.com/jminardi/mecode.git
$ cd mecode
$ python setup.py install
```

Optional Dependencies
---------------------
The following dependencies are optional, and are only needed for
interpolation and visualization. An easy way to install them is to use
[Canopy][0] or [conda][1].

* numpy
    + numpy is needed for interpolation and visualization
* scipy
    + scipy is used for interpolation
* mayavi
    + mayavi is used for visualization

[0]: https://www.enthought.com/products/canopy/
[1]: https://store.continuum.io/cshop/anaconda/

TODO
----
* split footer.txt into different files.
* replace "z" with arbitrary axis name on the fly.
* add pressure box comport to `__init__()` method
* is set_valve the best name?
* finalize interface on aerotech functions.
* build out multi-nozzle support
    * include multi-nozzle support in view method.
* factor out aerotech specific methods into their own class

Credits
-------
This software was developed by the [Lewis Lab][2] at Harvard University.

[2]: http://lewisgroup.seas.harvard.edu/

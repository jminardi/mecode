Mecode
======

[![Build Status](https://travis-ci.org/jminardi/mecode.svg?branch=master)](https://travis-ci.org/jminardi/mecode)

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
are writing to a file. This can be accomplished automatically by using G as
a context manager like so:

```python
with G(outfile='file.gcode') as g:
    g.move(10)
```

When the `with` block is exited, `g.teardown()` will be automatically called.

The resulting toolpath can be visualized in 3D using the `mayavi` or `matplotlib`
package with the `view()` method:

```python
g = G()
g.meander(10, 10, 1)
g.view()
```

The graphics backend can be specified when calling the `view()` method, e.g. `g.view('matplotlib')`.
`mayavi` is the default graphics backend.

All GCode Methods
-----------------

All methods have detailed docstrings and examples.

* `set_home()`
* `reset_home()`
* `feed()`
* `dwell()`
* `home()`
* `move()`
* `abs_move()`
* `arc()`
* `abs_arc()`
* `rect()`
* `meander()`
* `clip()`
* `triangular_wave()`

Matrix Transforms
-----------------

A wrapper class, `GMatrix` will run all move and arc commands through a 
2D transformation matrix before forwarding them to `G`.

To use, simply instantiate a `GMatrix` object instead of a `G` object:

```python
g = GMatrix()
g.push_matrix()      # save the current transformation matrix on the stack.
g.rotate(math.pi/2)  # rotate our transformation matrix by 90 degrees.
g.move(0, 1)         # same as moves (1,0) before the rotate.
g.pop_matrix()       # revert to the prior transformation matrix.
```

The transformation matrix is 2D instead of 3D to simplify arc support.

Renaming Axes
-------------

When working with a machine that has more than one Z-Axis, it is
useful to use the `rename_axis()` function. That way your code can
always refer to the verticle axis as 'Z', but you can dynamically
rename it.

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
visualization. An easy way to install them is to use
[Canopy][0] or [conda][1].

* numpy
* mayavi
* matplotlib

[0]: https://www.enthought.com/products/canopy/
[1]: https://store.continuum.io/cshop/anaconda/

TODO
----
* add pressure box comport to `__init__()` method
* build out multi-nozzle support
    * include multi-nozzle support in view method.
* factor out aerotech specific methods into their own class

Credits
-------
This software was developed by the [Lewis Lab][2] at Harvard University.

[2]: http://lewisgroup.seas.harvard.edu/

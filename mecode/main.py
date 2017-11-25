"""
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
desired tool path. ::

    from mecode import G
    g = G()
    g.move(10, 10)  # move 10mm in x and 10mm in y
    g.arc(x=10, y=5, radius=20, direction='CCW')  # counterclockwise arc with a radius of 20
    g.meander(5, 10, spacing=1)  # trace a rectangle meander with 1mm spacing between the passes
    g.abs_move(x=1, y=1)  # move the tool head to position (1, 1)
    g.home()  # move the tool head to the origin (0, 0)

By default `mecode` simply prints the generated GCode to stdout. If instead you
want to generate a file, you can pass a filename. ::

    g = G(outfile='path/to/file.gcode')

*NOTE:* When using the option direct_write=True or when writing to a file, 
`g.teardown()` must be called after all commands are executed. If you
are writing to a file, this can be accomplished automatically by using G as
a context manager like so:

```python
with G(outfile='file.gcode') as g:
    g.move(10)
```

When the `with` block is exited, `g.teardown()` will be automatically called.

The resulting toolpath can be visualized in 3D with
the `view()` method ::

    g = G()
    g.meander(10, 10, 1)
    g.view()

* *Author:* Jack Minardi
* *Email:* jack@minardi.org

This software was developed by the Lewis Lab at Harvard University and Voxel8 Inc.

"""

import math
import os
from collections import defaultdict

from printer import Printer

HERE = os.path.dirname(os.path.abspath(__file__))

# for python 2/3 compatibility
try:
    isinstance("", basestring)

    def is_str(s):
        return isinstance(s, basestring)

    def encode2To3(s):
        return s

    def decode2To3(s):
        return s

except NameError:

    def is_str(s):
        return isinstance(s, str)

    def encode2To3(s):
        return bytes(s, 'UTF-8')

    def decode2To3(s):
        return s.decode('UTF-8')


class G(object):

    def __init__(self, outfile=None, print_lines='auto', header=None, footer=None,
                 aerotech_include=False,
                 output_digits=6,
                 direct_write=False,
                 direct_write_mode='socket',
                 printer_host='localhost',
                 printer_port=8000,
                 baudrate=250000,
                 two_way_comm=True,
                 x_axis='X',
                 y_axis='Y',
                 z_axis='Z',
                 i_axis='I',
                 j_axis='J',
                 k_axis='K',
                 extrude=False,
                 filament_diameter=1.75,
                 layer_height=0.19,
                 extrusion_width=0.35,
                 extrusion_multiplier=1,
                 setup=True,
                 lineend='os',
                 comment_char=';'):
        """
        Parameters
        ----------
        outfile : path or None (default: None)
            If a path is specified, the compiled gcode will be writen to that
            file.
        print_lines : bool (default: 'auto')
            Whether or not to print the compiled GCode to stdout. If set to
            'auto' then lines will be printed if no outfile given.
        header : path or None (default: None)
            Optional path to a file containing lines to be written at the
            beginning of the output file
        footer : path or None (default: None)
            Optional path to a file containing lines to be written at the end
            of the output file.
        aerotech_include : bool (default: False)
            If true, add aerotech specific functions and var defs to outfile.
        output_digits : int (default: 6)
            How many digits to include after the decimal in the output gcode.
        direct_write : bool (default: False)
            If True a socket or serial port is opened to the printer and the
            GCode is sent directly over.
        direct_write_mode : str (either 'socket' or 'serial') (default: socket)
            Specify the channel your printer communicates over, only used if
            `direct_write` is True.
        printer_host : str (default: 'localhost')
            Hostname of the printer, only used if `direct_write` is True.
        printer_port : int (default: 8000)
            Port of the printer, only used if `direct_write` is True.
        baudrate: int (default: 250000)
            The baudrate to connect to the printer with.
        two_way_comm : bool (default: True)
            If True, mecode waits for a response after every line of GCode is
            sent over the socket. The response is returned by the `write`
            method. Only applies if `direct_write` is True.
        x_axis : str (default 'X')
            The name of the x axis (used in the exported gcode)
        y_axis : str (default 'Y')
            The name of the z axis (used in the exported gcode)
        z_axis : str (default 'Z')
            The name of the z axis (used in the exported gcode)
        i_axis : str (default 'I')
            The name of the i axis (used in the exported gcode)
        j_axis : str (default 'J')
            The name of the j axis (used in the exported gcode)
        k_axis : str (default 'K')
            The name of the k axis (used in the exported gcode)
        extrude : True or False (default: False)
            If True, a flow calculation will be done in the move command. The
            neccesary length of filament to be pushed through on a move command
            will be tagged on as a kwarg. ex. X5 Y5 E3
        filament_diameter: float (default 1.75)
            the diameter of FDM filament you are using
        layer_height : float
            Layer height for FDM printing. Only relavent when extrude = True.
        extrusion width: float
            total width of the capsule shaped cross section of a squashed filament.
        extrusion_multiplier: float (default = 1)
            The length of extrusion filament to be pushed through on a move
            command will be multiplied by this number before being applied.
        setup : Bool (default: True)
            Whether or not to automatically call the setup function.
        lineend : str (default: 'os')
            Line ending to use when writing to a file or printer. The special
            value 'os' can be passed to fall back on python's automatic
            lineending insertion.
        comment_char : str (default: ';')
            Character to use when outputting comments.

        """
        self.outfile = outfile
        self.print_lines = print_lines
        self.header = header
        self.footer = footer
        self.aerotech_include = aerotech_include
        self.output_digits = output_digits
        self.direct_write = direct_write
        self.direct_write_mode = direct_write_mode
        self.printer_host = printer_host
        self.printer_port = printer_port
        self.baudrate = baudrate
        self.two_way_comm = two_way_comm
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.z_axis = z_axis
        self.i_axis = i_axis
        self.j_axis = j_axis
        self.k_axis = k_axis
        self.comment_char = comment_char

        self._current_position = defaultdict(float)
        self.is_relative = True

        self.extrude = extrude
        self.filament_diameter = filament_diameter
        self.layer_height = layer_height
        self.extrusion_width = extrusion_width
        self.extrusion_multiplier = extrusion_multiplier

        self.position_history = [(0, 0, 0)]
        self.color_history = [(0, 0, 0)]
        self.speed = 0
        self.speed_history = []

        self._socket = None
        self._p = None

        # If the user passes in a line ending then we need to open the output
        # file in binary mode, otherwise python will try to be smart and
        # convert line endings in a platform dependent way.
        if lineend == 'os':
            mode = 'w+'
            self.lineend = '\n'
        else:
            mode = 'wb+'
            self.lineend = lineend

        if is_str(outfile):
            self.out_fd = open(outfile, mode)
        elif outfile is not None:  # if outfile not str assume it is an open file
            self.out_fd = outfile
        else:
            self.out_fd = None

        if setup:
            self.setup()

    @property
    def current_position(self):
        return self._current_position

    def __enter__(self):
        """
        Context manager entry
        Can use like:

        with mecode.G(  outfile=self.outfile,
                        print_lines=False,
                        aerotech_include=False) as g:
            <code block>
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit
        """
        self.teardown()

    # GCode Aliases  ########################################################

    def set_home(self, x=None, y=None, z=None, **kwargs):
        """ Set the current position to the given position without moving.

        Example
        -------
        >>> # set the current position to X=0, Y=0
        >>> g.set_home(0, 0)

        """
        args = self._format_args(x, y, z, **kwargs)
        space = ' ' if len(args) > 0 else ''
        self.write('G92' + space + args + ' {}set home'.format(self.comment_char))

        self._update_current_position(mode='absolute', x=x, y=y, z=z, **kwargs)

    def reset_home(self):
        """ Reset the position back to machine coordinates without moving.
        """
        # FIXME This does not work with internal current_position
        # FIXME You must call an abs_move after this to re-sync
        # current_position
        self.write('G92.1 {}reset position to machine coordinates without moving'.format(self.comment_char))

    def relative(self):
        """ Enter relative movement mode, in general this method should not be
        used, most methods handle it automatically.

        """
        if not self.is_relative:
            self.write('G91 {}relative'.format(self.comment_char))
            self.is_relative = True

    def absolute(self):
        """ Enter absolute movement mode, in general this method should not be
        used, most methods handle it automatically.

        """
        if self.is_relative:
            self.write('G90 {}absolute'.format(self.comment_char))
            self.is_relative = False

    def feed(self, rate):
        """ Set the feed rate (tool head speed) in (typically) mm/minute

        Parameters
        ----------
        rate : float
            The speed to move the tool head in (typically) mm/minute.

        """
        self.write('G1 F{}'.format(rate))
        self.speed = rate

    def dwell(self, time):
        """ Pause code executions for the given amount of time.

        Parameters
        ----------
        time : float
            Time in milliseconds to pause code execution.

        """
        self.write('G4 P{}'.format(time))

    # Composed Functions  #####################################################

    def setup(self):
        """ Set the environment into a consistent state to start off. This
        method must be called before any other commands.

        """
        self._write_header()
        if self.is_relative:
            self.write('G91 {}relative'.format(self.comment_char))
        else:
            self.write('G90 {}absolute'.format(self.comment_char))

    def teardown(self, wait=True):
        """ Close the outfile file after writing the footer if opened. This
        method must be called once after all commands.

        Parameters
        ----------
        wait : Bool (default: True)
            Only used if direct_write_model == 'serial'. If True, this method
            waits to return until all buffered lines have been acknowledged.

        """
        if self.out_fd is not None:
            if self.aerotech_include is True:
                with open(os.path.join(HERE, 'footer.txt')) as fd:
                    self._write_out(lines=fd.readlines())
            if self.footer is not None:
                with open(self.footer) as fd:
                    self._write_out(lines=fd.readlines())
            if self.outfile is None:
                self.out_fd.close()
        if self._socket is not None:
            self._socket.close()
        if self._p is not None:
            self._p.disconnect(wait)

    def home(self):
        """ Move the tool head to the home position (X=0, Y=0).
        """
        self.abs_move(x=0, y=0)

    def move(self, x=None, y=None, z=None, rapid=False, color=0, **kwargs):
        """ Move the tool head to the given position. This method operates in
        relative mode unless a manual call to `absolute` was given previously.
        If an absolute movement is desired, the `abs_move` method is
        recommended instead.

        Examples
        --------
        >>> # move the tool head 10 mm in x and 10 mm in y
        >>> g.move(x=10, y=10)
        >>> # the x, y, and z keywords may be omitted:
        >>> g.move(10, 10, 10)

        >>> # move the A axis up 20 mm
        >>> g.move(A=20)

        """
        if self.extrude is True and 'E' not in kwargs.keys():
            if self.is_relative is not True:
                x_move = self.current_position['x'] if x is None else x
                y_move = self.current_position['y'] if y is None else y
                x_distance = abs(x_move - self.current_position['x'])
                y_distance = abs(y_move - self.current_position['y'])
                current_extruder_position = self.current_position['E']
            else:
                x_distance = 0 if x is None else x
                y_distance = 0 if y is None else y
                current_extruder_position = 0
            line_length = math.sqrt(x_distance**2 + y_distance**2)
            area = self.layer_height*(self.extrusion_width-self.layer_height) + \
                3.14159*(self.layer_height/2)**2
            volume = line_length*area
            filament_length = ((4*volume)/(3.14149*self.filament_diameter**2))*self.extrusion_multiplier
            kwargs['E'] = filament_length + current_extruder_position

        self._update_current_position(x=x, y=y, z=z, color=color, **kwargs)
        args = self._format_args(x, y, z, **kwargs)
        cmd = 'G0 ' if rapid else 'G1 '
        self.write(cmd + args)

    def abs_move(self, x=None, y=None, z=None, rapid=False, **kwargs):
        """ Same as `move` method, but positions are interpreted as absolute.
        """
        if self.is_relative:
            self.absolute()
            self.move(x=x, y=y, z=z, rapid=rapid, **kwargs)
            self.relative()
        else:
            self.move(x=x, y=y, z=z, rapid=rapid, **kwargs)

    def rapid(self, x=None, y=None, z=None, **kwargs):
        """ Executes an uncoordinated move to the specified location.
        """
        self.move(x, y, z, rapid=True, **kwargs)

    def abs_rapid(self, x=None, y=None, z=None, **kwargs):
        """ Executes an uncoordinated abs move to the specified location.
        """
        self.abs_move(x, y, z, rapid=True, **kwargs)

    def retract(self, retraction):
        if self.extrude is False:
            self.move(E = -retraction)
        else:
            self.extrude = False
            self.move(E = -retraction)
            self.extrude = True

    def arc(self, x=None, y=None, z=None, direction='CW', radius='auto',
            helix_dim=None, helix_len=0, **kwargs):
        """ Arc to the given point with the given radius and in the given
        direction. If helix_dim and helix_len are specified then the tool head
        will also perform a linear movement through the given dimension while
        completing the arc.

        Parameters
        ----------
        points : floats
            Must specify two points as kwargs, e.g. x=5, y=5
        direction : str (either 'CW' or 'CCW') (default: 'CW')
            The direction to execute the arc in.
        radius : 'auto' or float (default: 'auto')
            The radius of the arc. A negative value will select the longer of
            the two possible arc segments. If auto is selected the radius will
            be set to half the linear distance to desired point.
        helix_dim : str or None (default: None)
            The linear dimension to complete the helix through
        helix_len : float
            The length to move in the linear helix dimension.

        Examples
        --------
        >>> # arc 10 mm up in y and 10 mm over in x with a radius of 20.
        >>> g.arc(x=10, y=10, radius=20)

        >>> # move 10 mm up on the A axis, arcing through y with a radius of 20
        >>> g.arc(A=10, y=0, radius=20)

        >>> # arc through x and y while moving linearly on axis A
        >>> g.arc(x=10, y=10, radius=50, helix_dim='A', helix_len=5)

        """
        dims = dict(kwargs)
        if x is not None:
            dims['x'] = x
        if y is not None:
            dims['y'] = y
        if z is not None:
            dims['z'] = z
        msg = 'Must specify two of x, y, or z.'
        if len(dims) != 2:
            raise RuntimeError(msg)
        dimensions = [k.lower() for k in dims.keys()]
        if 'x' in dimensions and 'y' in dimensions:
            plane_selector = 'G17 {}XY plane'.format(self.comment_char)  # XY plane
            axis = helix_dim
        elif 'x' in dimensions:
            plane_selector = 'G18 {}XZ plane'.format(self.comment_char)  # XZ plane
            dimensions.remove('x')
            axis = dimensions[0].upper()
        elif 'y' in dimensions:
            plane_selector = 'G19 {}YZ plane'.format(self.comment_char)  # YZ plane
            dimensions.remove('y')
            axis = dimensions[0].upper()
        else:
            raise RuntimeError(msg)
        if self.z_axis != 'Z':
            axis = self.z_axis

        if direction == 'CW':
            command = 'G2'
        elif direction == 'CCW':
            command = 'G3'

        values = [v for v in dims.values()]
        if self.is_relative:
            dist = math.sqrt(values[0] ** 2 + values[1] ** 2)
        else:
            k = [ky for ky in dims.keys()]
            cp = self._current_position
            dist = math.sqrt(
                (cp[k[0]] - values[0]) ** 2 + (cp[k[1]] - values[1]) ** 2
            )
        if radius == 'auto':
            radius = dist / 2.0
        elif abs(radius) < dist / 2.0:
            msg = 'Radius {} to small for distance {}'.format(radius, dist)
            raise RuntimeError(msg)

        #extrude feature implementation
        # only designed for flow calculations in x-y plane
        if self.extrude is True:
            area = self.layer_height*(self.extrusion_width-self.layer_height) + 3.14159*(self.layer_height/2)**2
            if self.is_relative is not True:
                current_extruder_position = self.current_position['E']
            else:
                current_extruder_position = 0

            circle_circumference = 2*3.14159*abs(radius)

            arc_angle = ((2*math.asin(dist/(2*abs(radius))))/(2*3.14159))*360
            shortest_arc_length = (arc_angle/180)*3.14159*abs(radius)
            if radius > 0:
                arc_length = shortest_arc_length
            else:
                arc_length = circle_circumference - shortest_arc_length
            volume = arc_length*area
            filament_length = ((4*volume)/(3.14149*self.filament_diameter**2))*self.extrusion_multiplier
            dims['E'] = filament_length + current_extruder_position

        if axis is not None:
            self.write('G16 X Y {} {}coordinate axis assignment'.format(axis, self.comment_char))  # coordinate axis assignment
        self.write(plane_selector)
        args = self._format_args(**dims)
        if helix_dim is None:
            self.write('{0} {1} R{2:.{digits}f}'.format(command, args, radius,
                                                        digits=self.output_digits))
        else:
            self.write('{0} {1} R{2:.{digits}f} G1 {3}{4}'.format(
                command, args, radius, helix_dim.upper(), helix_len, digits=self.output_digits))
            dims[helix_dim] = helix_len

        self._update_current_position(**dims)


    def arc_ijk(self, target, center, plane, direction='CW', helix_len=None):
        """ Arc to the given point with the given radius and in the given
        direction. If helix_dim and helix_len are specified then the tool head
        will also perform a linear movement along the axis orthogonal to the
        arc plane while completing the arc.

        Parameters
        ----------
        plane : str ('xy', 'yz', 'xz')
            Plane in which the arc is drawn
        target : 2-tuple of coordinates
            the end point of the arc, on the relevant plane
        center : 2-tuple of coordinates
            the distance to the center point of the arc from the
            starting position, on the relevant plane
        direction : str (either 'CW' or 'CCW') (default: 'CW')
            The direction to execute the arc in.
        helix_len : float
            The distance to move along the axis orthogonal to the arc plane
            during the arc.

        """

        if len(target) != 2:
            raise RuntimeError("'target' must be a 2-tuple of numbers (passed %s)" % target)
        if len(center) != 2:
            raise RuntimeError("'center' must be a 2-tuple of numbers (passed %s)" % center)

        if plane == 'xy':
            self.write('G17 {}XY plane'.format(self.comment_char))  # XY plane
            dims = {
                'x' : target[0],
                'y' : target[1],
                'i' : center[0],
                'j' : center[1],
            }
            if helix_len:
                dims['z'] = helix_len
        elif plane == 'yz':
            self.write('G19 {}YZ plane'.format(self.comment_char))  # YZ plane
            dims = {
                'y' : target[0],
                'z' : target[1],
                'j' : center[0],
                'k' : center[1],
            }
            if helix_len:
                dims['x'] = helix_len
        elif plane == 'xz':
            self.write('G18 {}XZ plane'.format(self.comment_char))  # XZ plane
            dims = {
                'x' : target[0],
                'z' : target[1],
                'i' : center[0],
                'k' : center[1],
            }
            if helix_len:
                dims['y'] = helix_len
        else:
            raise RuntimeError("Selected plane ('%s') is not one of ('xy', 'yz', 'xz')!" % plane)

        if direction == 'CW':
            command = 'G2'
        elif direction == 'CCW':
            command = 'G3'


        args = self._format_args(**dims)

        self.write('{} {}'.format(command, args))

        self._update_current_position(**dims)

    def abs_arc(self, direction='CW', radius='auto', **kwargs):
        """ Same as `arc` method, but positions are interpreted as absolute.
        """
        if self.is_relative:
            self.absolute()
            self.arc(direction=direction, radius=radius, **kwargs)
            self.relative()
        else:
            self.arc(direction=direction, radius=radius, **kwargs)

    def rect(self, x, y, direction='CW', start='LL'):
        """ Trace a rectangle with the given width and height.

        Parameters
        ----------
        x : float
            The width of the rectangle in the x dimension.
        y : float
            The height of the rectangle in the y dimension.
        direction : str (either 'CW' or 'CCW') (default: 'CW')
            Which direction to complete the rectangle in.
        start : str (either 'LL', 'UL', 'LR', 'UR') (default: 'LL')
            The start of the rectangle -  L/U = lower/upper, L/R = left/right
            This assumes an origin in the lower left.

        Examples
        --------
        >>> # trace a 10x10 clockwise square, starting in the lower left corner
        >>> g.rect(10, 10)

        >>> # 1x5 counterclockwise rect starting in the upper right corner
        >>> g.rect(1, 5, direction='CCW', start='UR')

        """
        if direction == 'CW':
            if start.upper() == 'LL':
                self.move(y=y)
                self.move(x=x)
                self.move(y=-y)
                self.move(x=-x)
            elif start.upper() == 'UL':
                self.move(x=x)
                self.move(y=-y)
                self.move(x=-x)
                self.move(y=y)
            elif start.upper() == 'UR':
                self.move(y=-y)
                self.move(x=-x)
                self.move(y=y)
                self.move(x=x)
            elif start.upper() == 'LR':
                self.move(x=-x)
                self.move(y=y)
                self.move(x=x)
                self.move(y=-y)
        elif direction == 'CCW':
            if start.upper() == 'LL':
                self.move(x=x)
                self.move(y=y)
                self.move(x=-x)
                self.move(y=-y)
            elif start.upper() == 'UL':
                self.move(y=-y)
                self.move(x=x)
                self.move(y=y)
                self.move(x=-x)
            elif start.upper() == 'UR':
                self.move(x=-x)
                self.move(y=-y)
                self.move(x=x)
                self.move(y=y)
            elif start.upper() == 'LR':
                self.move(y=y)
                self.move(x=-x)
                self.move(y=-y)
                self.move(x=x)

    def meander(self, x, y, spacing, start='LL', orientation='x', tail=False,
                minor_feed=None):
        """ Infill a rectangle with a square wave meandering pattern. If the
        relevant dimension is not a multiple of the spacing, the spacing will
        be tweaked to ensure the dimensions work out.

        Parameters
        ----------
        x : float
            The width of the rectangle in the x dimension.
        y : float
            The height of the rectangle in the y dimension.
        spacing : float
            The space between parallel meander lines.
        start : str (either 'LL', 'UL', 'LR', 'UR') (default: 'LL')
            The start of the meander -  L/U = lower/upper, L/R = left/right
            This assumes an origin in the lower left.
        orientation : str ('x' or 'y') (default: 'x')
        tail : Bool (default: False)
            Whether or not to terminate the meander in the minor axis
        minor_feed : float or None (default: None)
            Feed rate to use in the minor axis

        Examples
        --------
        >>> # meander through a 10x10 square with a spacing of 1mm starting in
        >>> # the lower left.
        >>> g.meander(10, 10, 1)

        >>> # 3x5 meander with a spacing of 1 and with parallel lines through y
        >>> g.meander(3, 5, spacing=1, orientation='y')

        >>> # 10x5 meander with a spacing of 2 starting in the upper right.
        >>> g.meander(10, 5, 2, start='UR')

        """
        if start.upper() == 'UL':
            x, y = x, -y
        elif start.upper() == 'UR':
            x, y = -x, -y
        elif start.upper() == 'LR':
            x, y = -x, y

        # Major axis is the parallel lines, minor axis is the jog.
        if orientation == 'x':
            major, major_name = x, 'x'
            minor, minor_name = y, 'y'
        else:
            major, major_name = y, 'y'
            minor, minor_name = x, 'x'

        actual_spacing = self._meander_spacing(minor, spacing)
        if abs(actual_spacing) != spacing:
            msg = '{}WARNING! meander spacing updated from {} to {}'
            self.write(msg.format(self.comment_char, spacing, actual_spacing))
        spacing = actual_spacing
        sign = 1

        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        major_feed = self.speed
        if not minor_feed:
            minor_feed = self.speed
        for _ in range(int(self._meander_passes(minor, spacing))):
            self.move(**{major_name: (sign * major)})
            if minor_feed != major_feed:
                self.feed(minor_feed)
            self.move(**{minor_name: spacing})
            if minor_feed != major_feed:
                self.feed(major_feed)
            sign = -1 * sign
        if tail is False:
            self.move(**{major_name: (sign * major)})

        if was_absolute:
            self.absolute()

    def clip(self, axis='z', direction='+x', height=4):
        """ Move the given axis up to the given height while arcing in the
        given direction.

        Parameters
        ----------
        axis : str (default: 'z')
            The axis to move, e.g. 'z'
        direction : str (either +-x or +-y) (default: '+x')
            The direction to arc through
        height : float (default: 4)
            The height to end up at

        Examples
        --------
        >>> # move 'z' axis up 4mm while arcing through positive x
        >>> g.clip()

        >>> # move 'A' axis up 10mm while arcing through negative y
        >>> g.clip('A', height=10, direction='-y')

        """
        secondary_axis = direction[1]
        if height > 0:
            orientation = 'CW' if direction[0] == '-' else 'CCW'
        else:
            orientation = 'CCW' if direction[0] == '-' else 'CW'
        radius = abs(height / 2.0)
        kwargs = {
            secondary_axis: 0,
            axis: height,
            'direction': orientation,
            'radius': radius,
        }
        self.arc(**kwargs)

    def triangular_wave(self, x, y, cycles, start='UR', orientation='x'):
        """ Perform a triangular wave.

        Parameters
        ----------
        x : float
            The length to move in x in one half cycle
        y : float
            The length to move in y in one half cycle
        start : str (either 'LL', 'UL', 'LR', 'UR') (default: 'UR')
            The start of the zigzag direction.
            This assumes an origin in the lower left, and move toward upper
            right.
        orientation : str ('x' or 'y') (default: 'x')

        Examples
        --------
        >>> # triangular wave for one cycle going 10 in x and 10 in y per half
        >>> # cycle.
        >>> # the lower left.
        >>> g.zigzag(10, 10, 1)

        >>> # triangular wave 4 cycles, going 3 in x and 5 in y per half cycle,
        >>> # oscillating along the y axis.
        >>> g.zigzag(3, 5, 4, orientation='y')

        >>> # triangular wave 2 cycles, going 10 in x and 5 in y per half cycle,
        >>> # oscillating along the x axis making the first half cycle towards
        >>> # the lower left corner of the movement area.
        >>> g.zigzag(10, 5, 2, start='LL')

        """
        if start.upper() == 'UL':
            x, y = -x, y
        elif start.upper() == 'LL':
            x, y = -x, -y
        elif start.upper() == 'LR':
            x, y = x, -y

        # Major axis is the parallel lines, minor axis is the jog.
        if orientation == 'x':
            major, major_name = x, 'x'
            minor, minor_name = y, 'y'
        else:
            major, major_name = y, 'y'
            minor, minor_name = x, 'x'

        sign = 1

        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        for _ in range(int(cycles*2)):
            self.move(**{minor_name: (sign * minor), major_name: major})
            sign = -1 * sign

        if was_absolute:
            self.absolute()

    def spiral(self, end_diameter, spacing, start='center', direction='CW', 
                step_angle = 0.1, start_diameter = 0):
        """ Performs an Archimedean spiral. Start by moving to the center of the spiral location
        then use the 'start' argument to specify a starting location (either center or edge).

        Parameters
        ----------
        end_diameter : float
            The outer diameter of the spiral.
        spacing : float
            The spacing between lines of the spiral.
        start_diameter : float
            The inner diameter of the spiral (default: 0).
        step_angle : float
            Resolution of the spiral in radians, smaller is higher resolution (default: 0.1).
        start : str (either 'center', 'edge')
            The location to start the spiral (default: 'center').
        direction : str (either 'CW', 'CCW')
            Direction to print the spiral, either clockwise or counterclockwise. (default: 'CW')

        Examples
        --------
        >>> # move to origin
        >>> g.absolute()
        >>> g.move(x=0, y=0)

        >>> # start first spiral, outer diameter of 20, spacing of 1
        >>> g.spiral(20,1)

        >>> # move to second spiral location and do similar spiral but start at edge
        >>> g.move(x=50,y=0)
        >>> g.spiral(20,1,start='edge')

        >>> # move to third spiral location, this time starting at edge but printing CCW
        >>> g.move(y=50,x=50)
        >>> g.spiral(20,1,start='edge',direction='CCW')
        
        >>> # move to fourth spiral location, starting at center again but printing CCW
        >>> g.move(x=0,y=50)
        >>> g.spiral(20,1,direction='CCW')
        
        """
        import numpy as np
        start_spiral_turns = (start_diameter/2.0)/spacing
        end_spiral_turns = (end_diameter/2.0)/spacing
        
        starting_position = [self._current_position['x'],self._current_position['y']]
        
        was_relative = True
        if self.is_relative:
            self.absolute()
        else:
            was_relative = False

        # SEE: https://www.comsol.com/blogs/how-to-build-a-parameterized-archimedean-spiral-geometry/
        b = spacing/(2*math.pi)
        t = np.arange(start_spiral_turns*2*math.pi, end_spiral_turns*2*math.pi, step_angle)
        #Add last final point to ensure correct outer diameter
        t = np.append(t,end_spiral_turns*2*math.pi)
        if start == 'center':
            pass
        elif start == 'edge':
            t = t[::-1]
        else:
            raise Exception("Must either choose 'center' or 'edge' for starting position.")
        for step in t:
            if (direction == 'CW' and start == 'center') or (direction == 'CCW' and start == 'edge'):
                x_move = -step*b*math.cos(step)+starting_position[0]
            elif (direction == 'CCW' and start == 'center') or (direction == 'CW' and start == 'edge'):
                x_move = step*b*math.cos(step)+starting_position[0]
            else:
                raise Exception("Must either choose 'CW' or 'CCW' for spiral direction.")
            y_move = step*b*math.sin(step)+starting_position[1]
            self.move(x_move, y_move)
            #self.write(";{}".format(2*((x_move-starting_position[0])**2+(y_move-starting_position[1])**2)**0.5))

        if was_relative:
                self.relative()

    def gradient_spiral(self, end_diameter, spacing, gradient, feedrate, flowrate, 
                start='center', direction='CW', step_angle = 0.1, start_diameter = 0,
                center_position=None, dead_delay=0):
        """ Identical motion to the regular spiral function, but with the control of two syringe pumps to enable control over
            dielectric properties over the course of the spiral. Starting with simply hitting certain dielectric constants at 
            different values along the radius of the spiral.

        Parameters
        ----------
        end_diameter : float
            The outer diameter of the spiral.
        spacing : float
            The spacing between lines of the spiral.
        gradient : str
            Functioning defining the ink concentration along the radius of the spiral
        feedrate : float
            Feedrate is the speed of the nozzle relative to the substrate
        flowrate : float
            Flowrate is a measure of the amount of ink dispensed per second by the syringe pump
        start : str (either 'center', 'edge')
            The location to start the spiral (default: 'center').
        direction : str (either 'CW', 'CCW')
            Direction to print the spiral, either clockwise or counterclockwise. (default: 'CW')
        step_angle : float
            Resolution of the spiral in radians, smaller is higher resolution (default: 0.1).
        start_diameter : float
            The inner diameter of the spiral (default: 0).
        center_position : list
            Position of the absolute center of the spiral, useful when starting a spiral at the edge of a completed spiral
        dead_delay : float
            Printing composition offset caused by the dead volume of the nozzle which creates a delayed
            effect between the syringe pumps and the actual composition of the ink exiting the nozzle.

        Examples
        --------
        >>> g.gradient_spiral(start_diameter=7.62, #mm
        ...     end_diameter=30.48, #mm
        ...     spacing=1, #mm
        ...     feedrate=8, #mm/s
        ...     flowrate=2/60.0, #rot/s
        ...     start='edge', #'edge' or 'center'
        ...     direction='CW', #'CW' or 'CCW'
        ...     gradient="-0.322*r**2 - 6.976*r + 131.892") #Any function
        """

        import numpy as np
        import sympy as sy

        def calculate_extrusion_values(radius, length, feed = feedrate, flow = flowrate, formula = gradient, delay = dead_delay, spacing = spacing, start = start, outer_radius = end_diameter/2.0, inner_radius=start_diameter/2.0):
            """Calculates the extrusion values for syringe pumps A & B during a move along the print path.
            """

            def exact_length(r0,r1,h):
                """Calculates the exact length of an archimedean given the spacing, inner and outer radii.
                SEE: http://www.giangrandi.ch/soft/spiral/spiral.shtml

                Parameters
                ----------
                r0 : float
                    The inner diameter of the spiral.
                r1 : float
                    The outer diameter of the spiral.
                h  : float
                    The spacing of the spiral.
                """
                #t0 & t1 are the respective diameters in terms of radians along the spiral.
                t0 = 2*math.pi*r0/h
                t1 = 2*math.pi*r1/h
                return h/(2.0*math.pi)*(t1/2.0*math.sqrt(t1**2+1)+1/2.0*math.log(t1+math.sqrt(t1**2+1))-t0/2.0*math.sqrt(t0**2+1)-1/2.0*math.log(t0+math.sqrt(t0**2+1)))


            def exact_radius(r_0,h,L):
                """Calculates the exact outer radius of an archimedean given the spacing, inner radius and the length.
                SEE: http://www.giangrandi.ch/soft/spiral/spiral.shtml

                Parameters
                ----------
                r0 : float
                    The inner radius of the spiral.
                h  : float
                    The spacing of the spiral.
                L  : float
                    The length of the spiral.
                """
                d_0 = r_0*2
                if d_0 == 0:
                    d_0 = 1e-10
                
                def exact_length(d0,d1,h):
                    """Calculates the exact length of an archimedean given the spacing, inner and outer diameters.
                    SEE: http://www.giangrandi.ch/soft/spiral/spiral.shtml

                    Parameters
                    ----------
                    d0 : float
                        The inner diameter of the spiral.
                    d1 : float
                        The outer diameter of the spiral.
                    h  : float
                        The spacing of the spiral.
                    """
                    #t0 & t1 are the respective diameters in terms of radians along the spiral.
                    t0 = math.pi*d0/h
                    t1 = math.pi*d1/h
                    return h/(2.0*math.pi)*(t1/2.0*math.sqrt(t1**2+1)+1/2.0*math.log(t1+math.sqrt(t1**2+1))-t0/2.0*math.sqrt(t0**2+1)-1/2.0*math.log(t0+math.sqrt(t0**2+1)))

                def exact_length_derivative(d,h):
                    """Calculates the derivative of the exact length of an archimedean at a given diameter and spacing.
                    SEE: http://www.giangrandi.ch/soft/spiral/spiral.shtml

                    Parameters
                    ----------
                    d : float
                        The diameter point of interest in the spiral.
                    h  : float
                        The spacing of the spiral.
                    """
                    #t is diameter of interest in terms of radians along the spiral.
                    t = math.pi*d/h
                    dl_dt = h/(2.0*math.pi)*((2*t**2+1)/(2*math.sqrt(t**2+1))+(t+math.sqrt(t**2+1))/(2*t*math.sqrt(t**2+1)+2*t**2+2))
                    dl_dd = h*dl_dt/math.pi
                    return dl_dd

                #Approximate radius (for first guess)
                N = (h-d_0+math.sqrt((d_0-h)**2+4*h*L/math.pi))/(2*h)
                D_1 = 2*N*h + d_0
                tol = 1e-10

                #Use Newton's Method to iterate until within tolerance
                while True:
                    f_df_dt = (exact_length(d_0,D_1,h)-L)/1000/exact_length_derivative(D_1,h)
                    if f_df_dt < tol:
                        break
                    D_1 -= f_df_dt   
                return D_1/2
        
            def rollover(val,limit,mode):
                if val < limit: 
                    if mode == 'max':
                        return val
                    elif mode == 'min':
                        return limit+(limit-val)
                    else:
                        raise ValueError("'{}' is an incorrect selection for the mode".format(mode))
                else:
                    if mode == 'max':
                        return limit-(val-limit)
                    elif mode == 'min':
                        return val
                    else:
                        raise ValueError("'{}' is an incorrect selection for the mode".format(mode))

            def minor_fraction_calc(e,e_a=300,e_b=2.3,n=0.102,sr=0.6):
                """Calculates the minor fraction (fraction of part b) required to achieve the
                specified dielectric value

                Parameters
                ----------
                e : float
                    Dielectric value of interest
                e_a  : float
                    Dielectric value of part a
                e_b. : float
                    Dielectric value of part b
                n  : float
                    Morphology factor
                sr : float
                    Fraction of SrTi03 in part a
                """
                return 1 - ((e-e_b)*((n-1)*e_b-n*e_a))/(sr*(e_b-e_a)*(n*(e-e_b)+e_b))
            
            """
            This is a key line of the extrusion values calculations.
            It starts off by calculating the exact length along the spiral for the current 
            radius, then adds/subtracts on the dead volume delay (in effect looking into the 
            future path) to this length, then recalculates the appropriate radius at this new 
            postiion. This is value is then used in the gradient function to determine the minor 
            fraction of the mixed elements. Note that if delay is 0, then this line will have no 
            effect. If the spiral is moving outwards it must add the dead volume delay, whereas if
            the spiral is moving inwards, it must subtract it.

            """
            if start == 'center':
                offset_radius = exact_radius(0,spacing,rollover(exact_length(0,radius,spacing)+delay,exact_length(0,outer_radius,spacing),'max'))
            else:
                offset_radius = exact_radius(0,spacing,rollover(exact_length(0,radius,spacing)-delay,exact_length(0,inner_radius,spacing),'min'))

            expr = sy.sympify(formula)
            r = sy.symbols('r')
            minor_fraction = np.clip(minor_fraction_calc(float(expr.subs(r,offset_radius))),0,1)
            line_flow = length/float(feed)*flow
            return [minor_fraction*line_flow,(1-minor_fraction)*line_flow,minor_fraction]

        #End of calculate_extrusion_values() function

        start_spiral_turns = (start_diameter/2.0)/spacing
        end_spiral_turns = (end_diameter/2.0)/spacing
        
        #Use current position as center position if none is specified
        if center_position is None:
            center_position = [self._current_position['x'],self._current_position['y']]
        
        #Keep track of whether currently in relative or absolute mode
        was_relative = True
        if self.is_relative:
            self.absolute()
        else:
            was_relative = False

        #SEE: https://www.comsol.com/blogs/how-to-build-a-parameterized-archimedean-spiral-geometry/
        b = spacing/(2*math.pi)
        t = np.arange(start_spiral_turns*2*math.pi, end_spiral_turns*2*math.pi, step_angle)
        
        #Add last final point to ensure correct outer diameter
        t = np.append(t,end_spiral_turns*2*math.pi)
        if start == 'center':
            pass
        elif start == 'edge':
            t = t[::-1]
        else:
            raise Exception("Must either choose 'center' or 'edge' for starting position.")
        
        #Move to starting positon
        if (direction == 'CW' and start == 'center') or (direction == 'CCW' and start == 'edge'):
            x_move = -t[0]*b*math.cos(t[0])+center_position[0]
        elif (direction == 'CCW' and start == 'center') or (direction == 'CW' and start == 'edge'):
            x_move = t[0]*b*math.cos(t[0])+center_position[0]
        else:
            raise Exception("Must either choose 'CW' or 'CCW' for spiral direction.")
        y_move = t[0]*b*math.sin(t[0])+center_position[1]
        self.move(x_move, y_move)

        #Start writing moves
        self.feed(feedrate)
        syringe_extrusion = np.array([0.0,0.0])

        #Zero a & b axis before printing, we do this so it can easily do multiple layers without quickly jumping back to 0
        #Would likely be useful to change this to relative coordinates at some point
        self.write('G92 a0 b0')

        for step in t[1:]:
            if (direction == 'CW' and start == 'center') or (direction == 'CCW' and start == 'edge'):
                x_move = -step*b*math.cos(step)+center_position[0]
            elif (direction == 'CCW' and start == 'center') or (direction == 'CW' and start == 'edge'):
                x_move = step*b*math.cos(step)+center_position[0]
            else:
                raise Exception("Must either choose 'CW' or 'CCW' for spiral direction.")
            y_move = step*b*math.sin(step)+center_position[1]
            
            radius_pos = np.sqrt((self._current_position['x']-center_position[0])**2 + (self._current_position['y']-center_position[1])**2)
            line_length = np.sqrt((x_move-self._current_position['x'])**2 + (y_move-self._current_position['y'])**2)
            extrusion_values = calculate_extrusion_values(radius_pos,line_length)
            syringe_extrusion += extrusion_values[:2]
            self.move(x_move, y_move, a=syringe_extrusion[0],b=syringe_extrusion[1],color=extrusion_values[2])

        #Set back to relative mode if it was previsously before command was called
        if was_relative:
                self.relative()

    def purge_meander(self, x, y, spacing, volume_fraction, start='LL', orientation='x',
            tail=False, minor_feed=None):
        flowrate = 0.033333
        self.write('FREERUN a {}'.format(flowrate*volume_fraction))
        self.write('FREERUN b {}'.format(flowrate*(1-volume_fraction)))
        self.meander(x, y, spacing, start=start, orientation=orientation,
            tail=tail, minor_feed=minor_feed)
        self.write('FREERUN a 0')
        self.write('FREERUN b 0')

    # AeroTech Specific Functions  ############################################

    def get_axis_pos(self, axis):
        """ Gets the current position of the specified `axis`.
        """
        cmd = 'AXISSTATUS({}, DATAITEM_PositionFeedback)'.format(axis.upper())
        pos = self.write(cmd)
        return float(pos)

    def set_cal_file(self, path):
        """ Dynamically applies the specified calibration file at runtime.

        Parameters
        ----------
        path : str
            The path specifying the aerotech calibration file.

        """
        self.write(r'LOADCALFILE "{}", 2D_CAL'.format(path))

    def toggle_pressure(self, com_port):
        self.write('Call togglePress P{}'.format(com_port))

    def set_pressure(self, com_port, value):
        self.write('Call setPress P{} Q{}'.format(com_port, value))

    def set_vac(self, com_port, value):
        self.write('Call setVac P{} Q{}'.format(com_port, value))

    def set_valve(self, num, value):
        self.write('$DO{}.0={}'.format(num, value))

    def omni_on(self, com_port):
        self.write('Call omniOn P{}'.format(com_port))

    def omni_off(self, com_port):
        self.write('Call omniOff P{}'.format(com_port))

    def omni_intensity(self, com_port, value):
        command = 'SIL{}'.format(value)
        data = self.calc_CRC8(command)
        self.write('$strtask4="{}"'.format(data))
        self.write('Call omniSetInt P{}'.format(com_port))

    def set_alicat_pressure(self,com_port,value):
        self.write('Call setAlicatPress P{} Q{}'.format(com_port, value))

    def calc_CRC8(self,data):
        CRC8 = 0
        for letter in list(bytearray(data)):
            for i in range(8):
                if (letter^CRC8)&0x01:
                    CRC8 ^= 0x18
                    CRC8 >>= 1
                    CRC8 |= 0x80
                else:
                    CRC8 >>= 1
                letter >>= 1
        return data +'{:02X}'.format(CRC8)

    # Public Interface  #######################################################

    def view(self, backend='matplotlib',outfile=None):
        """ View the generated Gcode.

        Parameters
        ----------
        backend : str (default: 'matplotlib')
            The plotting backend to use, one of 'matplotlib' or 'mayavi'.
            'matplotlib2d' has been addded to better visualize mixing.

        """
        import numpy as np
        import matplotlib.cm as cm
        history = np.array(self.position_history)
        color = self.color_history

        if backend == 'matplotlib':
            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.pyplot as plt
            fig = plt.figure()
            ax = fig.gca(projection='3d')

            for index in [x+3 for x in range(len(history[1:-1])-3)]:
                X, Y, Z = history[index-1:index+1, 0], history[index-1:index+1, 1], history[index-1:index+1, 2]                
                ax.plot(X, Y, Z,color = cm.inferno(color[index])[:-1])

            X, Y, Z = history[:, 0], history[:, 1], history[:, 2]

            # Hack to keep 3D plot's aspect ratio square. See SO answer:
            # http://stackoverflow.com/questions/13685386
            max_range = np.array([X.max()-X.min(),
                                  Y.max()-Y.min(),
                                  Z.max()-Z.min()]).max() / 2.0

            mean_x = X.mean()
            mean_y = Y.mean()
            mean_z = Z.mean()
            ax.set_xlim(mean_x - max_range, mean_x + max_range)
            ax.set_ylim(mean_y - max_range, mean_y + max_range)
            ax.set_zlim(mean_z - max_range, mean_z + max_range)

            if outfile = None:
                plt.show()
            else:
                plt.savefig(outfile,dpi=200)

        elif backend == 'matplotlib2d':
            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.pyplot as plt
            fig = plt.figure()
            #ax = fig.gca(projection='3d')
            ax = fig.gca()
            ax.set_aspect('equal')
            
            for index in [x+3 for x in range(len(history[1:-1])-3)]:
                X, Y, Z = history[index-1:index+1, 0], history[index-1:index+1, 1], history[index-1:index+1, 2]
                ax.plot(X, Y, color = cm.hot(color[1:-1][index])[:-1])

            X, Y, Z = history[:, 0], history[:, 1], history[:, 2]

            # Hack to keep 3D plot's aspect ratio square. See SO answer:
            # http://stackoverflow.com/questions/13685386
            max_range = np.array([X.max()-X.min(),
                                  Y.max()-Y.min(),
                                  Z.max()-Z.min()]).max() / 2.0

            mean_x = X.mean()
            mean_y = Y.mean()
            mean_z = Z.mean()
            ax.set_xlim(mean_x - max_range, mean_x + max_range)
            ax.set_ylim(mean_y - max_range, mean_y + max_range)

            if outfile = None:
                plt.show()
            else:
                plt.savefig(outfile,dpi=200)

        elif backend == 'mayavi':
            from mayavi import mlab
            mlab.plot3d(history[:, 0], history[:, 1], history[:, 2])
        else:
            raise Exception("Invalid plotting backend! Choose one of mayavi or matplotlib or matplotlib2d.")

    def write(self, statement_in, resp_needed=False):
        if self.print_lines is True or (self.print_lines == 'auto' and self.outfile is None):
            print(statement_in)
        self._write_out(statement_in)
        statement = encode2To3(statement_in + self.lineend)
        if self.direct_write is True:
            if self.direct_write_mode == 'socket':
                if self._socket is None:
                    import socket
                    self._socket = socket.socket(socket.AF_INET,
                                                socket.SOCK_STREAM)
                    self._socket.connect((self.printer_host, self.printer_port))
                self._socket.send(statement)
                if self.two_way_comm is True:
                    response = self._socket.recv(8192)
                    response = decode2To3(response)
                    if response[0] != '%':
                        raise RuntimeError(response)
                    return response[1:-1]
            elif self.direct_write_mode == 'serial':
                if self._p is None:
                    self._p = Printer(self.printer_port, self.baudrate)
                    self._p.connect()
                    self._p.start()
                if resp_needed:
                    return self._p.get_response(statement_in)
                else:
                    self._p.sendline(statement_in)

    def rename_axis(self, x=None, y=None, z=None):
        """ Replaces the x, y, or z axis with the given name.

        Examples
        --------
        >>> g.rename_axis(z='A')

        """
        if x is not None:
            self.x_axis = x
        elif y is not None:
            self.y_axis = y
        elif z is not None:
            self.z_axis = z
        else:
            msg = 'Must specify new name for x, y, or z only'
            raise RuntimeError(msg)

    # Private Interface  ######################################################

    def _write_out(self, line=None, lines=None):
        """ Writes given `line` or `lines` to the output file.
        """
        # Only write if user requested an output file.
        if self.out_fd is None:
            return

        if lines is not None:
            for line in lines:
                self._write_out(line)

        line = line.rstrip() + self.lineend  # add lineend character
        if hasattr(self.out_fd, 'mode') and 'b' in self.out_fd.mode:  # encode the string to binary if needed
            line = encode2To3(line)
        self.out_fd.write(line)


    def _meander_passes(self, minor, spacing):
        if minor > 0:
            passes = math.ceil(minor / spacing)
        else:
            passes = abs(math.floor(minor / spacing))
        return passes

    def _meander_spacing(self, minor, spacing):
        return minor / self._meander_passes(minor, spacing)

    def _write_header(self):
        if self.aerotech_include is True:
            with open(os.path.join(HERE, 'header.txt')) as fd:
                self._write_out(lines=fd.readlines())
        if self.header is not None:
            with open(self.header) as fd:
                self._write_out(lines=fd.readlines())

    def _format_args(self, x=None, y=None, z=None, i=None, j=None, k=None, **kwargs):
        d = self.output_digits
        args = []
        if x is not None:
            args.append('{0}{1:.{digits}f}'.format(self.x_axis, x, digits=d))
        if y is not None:
            args.append('{0}{1:.{digits}f}'.format(self.y_axis, y, digits=d))
        if z is not None:
            args.append('{0}{1:.{digits}f}'.format(self.z_axis, z, digits=d))
        if i is not None:
            args.append('{0}{1:.{digits}f}'.format(self.i_axis, i, digits=d))
        if j is not None:
            args.append('{0}{1:.{digits}f}'.format(self.j_axis, j, digits=d))
        if k is not None:
            args.append('{0}{1:.{digits}f}'.format(self.k_axis, k, digits=d))
        args += ['{0}{1:.{digits}f}'.format(k, kwargs[k], digits=d) for k in sorted(kwargs)]
        args = ' '.join(args)
        return args

    def _update_current_position(self, mode='auto', x=None, y=None, z=None, color = None,
                                 **kwargs):
        if mode == 'auto':
            mode = 'relative' if self.is_relative else 'absolute'

        if self.x_axis is not 'X' and x is not None:
            kwargs[self.x_axis] = x
        if self.y_axis is not 'Y' and y is not None:
            kwargs[self.y_axis] = y
        if self.z_axis is not 'Z' and z is not None:
            kwargs[self.z_axis] = z

        if mode == 'relative':
            if x is not None:
                self._current_position['x'] += x
            if y is not None:
                self._current_position['y'] += y
            if z is not None:
                self._current_position['z'] += z
            for dimention, delta in kwargs.items():
                self._current_position[dimention] += delta
        else:
            if x is not None:
                self._current_position['x'] = x
            if y is not None:
                self._current_position['y'] = y
            if z is not None:
                self._current_position['z'] = z
            for dimention, delta in kwargs.items():
                self._current_position[dimention] = delta

        x = self._current_position['x']
        y = self._current_position['y']
        z = self._current_position['z']

        self.position_history.append((x, y, z))
        self.color_history.append(color)

        len_history = len(self.position_history)
        if (len(self.speed_history) == 0
            or self.speed_history[-1][1] != self.speed):
            self.speed_history.append((len_history - 1, self.speed))

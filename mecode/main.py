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
    g.arc(x=10, y=5, radius=20, direction='CCW')  # counterclockwise arc with a radius of 5
    g.meander(5, 10, spacing=1)  # trace a rectangle meander with 1mm spacing between the passes
    g.abs_move(x=1, y=1)  # move the tool head to position (1, 1)
    g.home()  # move the tool head to the origin (0, 0)

By default `mecode` simply prints the generated GCode to stdout. If instead you
want to generate a file, you can pass a filename and turn off the printing when
instantiating the `G` object. ::

    g = G(outfile='path/to/file.gcode', print_lines=False)

*NOTE:* `g.teardown()` must be called after all commands are executed if you
are writing to a file.

The resulting toolpath can be visualized in 3D using the `mayavi` package with
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

from .printer import Printer

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

    def __init__(self, outfile=None, print_lines=True, header=None, footer=None,
                 aerotech_include=True, output_digits=6, direct_write=False,
                 direct_write_mode='socket', printer_host='localhost',
                 printer_port=8000, baudrate=250000, two_way_comm=True,
                 x_axis='X', y_axis='Y', z_axis='Z', extrude=False,
                 filament_diameter=1.75, layer_height=0.19,
                 extrusion_width=0.35, extrusion_multiplier=1, setup=True,
                 lineend='os'):
        """
        Parameters
        ----------
        outfile : path or None (default: None)
            If a path is specified, the compiled gcode will be writen to that
            file.
        print_lines : bool (default: True)
            Whether or not to print the compiled GCode to stdout
        header : path or None (default: None)
            Optional path to a file containing lines to be written at the
            beginning of the output file
        footer : path or None (default: None)
            Optional path to a file containing lines to be written at the end
            of the output file.
        aerotech_include : bool (default: True)
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

        """
        # string file name
        self.outfile = outfile if is_str(outfile) else None
        # file descriptor
        if not is_str(outfile) and outfile is not None:
            # assume arg outfile is passed in a file descriptor
            self.out_fd = outfile
        else:
            self.out_fd = None

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
        if lineend == 'os':
            self._open_as_binary = False
            self.lineend = '\n'
        else:
            self._open_as_binary = True
            self.lineend = lineend

        self._current_position = defaultdict(float)
        self.is_relative = True

        self.extrude = extrude
        self.filament_diameter = filament_diameter
        self.layer_height = layer_height
        self.extrusion_width = extrusion_width
        self.extrusion_multiplier = extrusion_multiplier

        self.position_history = [(0, 0, 0)]
        self.speed = 0
        self.speed_history = []

        self._socket = None
        self._p = None

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
        self.write('G92 ' + args)

        self._update_current_position(mode='absolute', x=x, y=y, z=z, **kwargs)

    def reset_home(self):
        """ Reset the position back to machine coordinates without moving.
        """
        # FIXME This does not work with internal current_position
        # FIXME You must call an abs_move after this to re-sync
        # current_position
        self.write('G92.1')

    def relative(self):
        """ Enter relative movement mode, in general this method should not be
        used, most methods handle it automatically.

        """
        if not self.is_relative:
            self.write('G91')
            self.is_relative = True

    def absolute(self):
        """ Enter absolute movement mode, in general this method should not be
        used, most methods handle it automatically.

        """
        if self.is_relative:
            self.write('G90')
            self.is_relative = False

    def feed(self, rate):
        """ Set the feed rate (tool head speed) in mm/s

        Parameters
        ----------
        rate : float
            The speed to move the tool head in mm/s.

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
            self.write('G91')
        else:
            self.write('G90')

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
                    lines = fd.readlines()
                    lines = [encode2To3(x.rstrip()+self.lineend) for x in lines]
                    self.out_fd.writelines(lines)
            if self.footer is not None:
                with open(self.footer) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x.rstrip()+self.lineend) for x in lines]
                    self.out_fd.writelines(lines)
            self.out_fd.close()
        if self._socket is not None:
            self._socket.close()
        if self._p is not None:
            self._p.disconnect(wait)

    def home(self):
        """ Move the tool head to the home position (X=0, Y=0).
        """
        self.abs_move(x=0, y=0)

    def move(self, x=None, y=None, z=None, rapid=False, **kwargs):
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

        self._update_current_position(x=x, y=y, z=z, **kwargs)
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
            plane_selector = 'G17'  # XY plane
            axis = helix_dim
        elif 'x' in dimensions:
            plane_selector = 'G18'  # XZ plane
            dimensions.remove('x')
            axis = dimensions[0].upper()
        elif 'y' in dimensions:
            plane_selector = 'G19'  # YZ plane
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
            self.write('G16 X Y {}'.format(axis))  # coordinate axis assignment
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
        >>> # meander through a 10x10 sqaure with a spacing of 1mm starting in
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
            msg = ';WARNING! meander spacing updated from {} to {}'
            self.write(msg.format(spacing, actual_spacing))
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
            self.feed(minor_feed)
            self.move(**{minor_name: spacing})
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

    # Public Interface  #######################################################

    def view(self, backend='mayavi'):
        """ View the generated Gcode.

        Parameters
        ----------
        backend : str (default: 'matplotlib')
            The plotting backend to use, one of 'matplotlib' or 'mayavi'.

        """
        import numpy as np
        history = np.array(self.position_history)

        if backend == 'matplotlib':
            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.pyplot as plt
            fig = plt.figure()
            ax = fig.gca(projection='3d')
            ax.set_aspect('equal')
            X, Y, Z = history[:, 0], history[:, 1], history[:, 2]
            ax.plot(X, Y, Z)

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

            plt.show()
        elif backend == 'mayavi':
            from mayavi import mlab
            mlab.plot3d(history[:, 0], history[:, 1], history[:, 2])
        else:
            raise Exception("Invalid plotting backend! Choose one of mayavi or matplotlib.")

    def write(self, statement_in, resp_needed=False):
        if self.print_lines:
            print(statement_in)
        statement = encode2To3(statement_in + self.lineend)
        if self.out_fd is not None:
            self.out_fd.write(statement)
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

    def _meander_passes(self, minor, spacing):
        if minor > 0:
            passes = math.ceil(minor / spacing)
        else:
            passes = abs(math.floor(minor / spacing))
        return passes

    def _meander_spacing(self, minor, spacing):
        return minor / self._meander_passes(minor, spacing)

    def _write_header(self):
        outfile = self.outfile
        if outfile is not None or self.out_fd is not None:
            if self.out_fd is None:  # open it if it is a path
                mode = 'wb+' if self._open_as_binary else 'w+'
                self.out_fd = open(outfile, mode)
            if self.aerotech_include is True:
                with open(os.path.join(HERE, 'header.txt')) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x.rstrip()+self.lineend) for x in lines]
                    self.out_fd.writelines(lines)
            if self.header is not None:
                with open(self.header) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x.rstrip()+self.lineend) for x in lines]
                    self.out_fd.writelines(lines)

    def _format_args(self, x=None, y=None, z=None, **kwargs):
        d = self.output_digits
        args = []
        if x is not None:
            args.append('{0}{1:.{digits}f}'.format(self.x_axis, x, digits=d))
        if y is not None:
            args.append('{0}{1:.{digits}f}'.format(self.y_axis, y, digits=d))
        if z is not None:
            args.append('{0}{1:.{digits}f}'.format(self.z_axis, z, digits=d))
        args += ['{0}{1:.{digits}f}'.format(k, kwargs[k], digits=d) for k in sorted(kwargs)]
        args = ' '.join(args)
        return args

    def _update_current_position(self, mode='auto', x=None, y=None, z=None,
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

        len_history = len(self.position_history)
        if (len(self.speed_history) == 0
            or self.speed_history[-1][1] != self.speed):
            self.speed_history.append((len_history - 1, self.speed))


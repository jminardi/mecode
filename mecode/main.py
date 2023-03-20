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
import sys
import numpy as np
from collections import defaultdict

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
        self.extruding = [None,False]
        self.extruding_history = []

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
                    self._write_out(lines=fd.readlines())
            if self.footer is not None:
                with open(self.footer) as fd:
                    self._write_out(lines=fd.readlines())
            self.out_fd.close()
        if self._socket is not None:
            self._socket.close()
        if self._p is not None:
            self._p.disconnect(wait)

    def home(self):
        """ Move the tool head to the home position (X=0, Y=0).
        """
        self.abs_move(x=0, y=0)

    def move(self, x=None, y=None, z=None, rapid=False, color=(0,0,0,0.5), **kwargs):
        """ Move the tool head to the given position. This method operates in
        relative mode unless a manual call to `absolute` was given previously.
        If an absolute movement is desired, the `abs_move` method is
        recommended instead.

        points : floats
            Must specify endpoint as kwargs, e.g. x=5, y=5
        rapid : Bool (default: False)
            Executes an uncoordinated move to the specified location.
        color : hex string or rgb(a) string
            Specifies a color to be added to color history for viewing.

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
            helix_dim=None, helix_len=0, linearize=True, **kwargs):
        """ Arc to the given point with the given radius and in the given
        direction. If helix_dim and helix_len are specified then the tool head
        will also perform a linear movement through the given dimension while
        completing the arc. Note: Helix and flow calculation do not currently 
        work with linearize.

        Parameters
        ----------
        points : floats
            Must specify endpoint as kwargs, e.g. x=5, y=5
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
        linearize : Bool (default: True)
            Represent the arc as a series of straight lines.

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
            if radius == 'auto':
                radius = dist / 2.0
            elif abs(radius) < dist / 2.0:
                msg = 'Radius {} to small for distance {}'.format(radius, dist)
                raise RuntimeError(msg)
            vect_dir= [values[0]/dist,values[1]/dist]
            if direction == 'CW':
                arc_rotation_matrix = np.matrix([[0, -1],[1, 0]])
            elif direction =='CCW':
                arc_rotation_matrix = np.matrix([[0, 1],[-1, 0]])
            perp_vect_dir = np.array(vect_dir)*arc_rotation_matrix
            a_vect= np.array([values[0]/2,values[1]/2])
            b_length = math.sqrt(radius**2-(dist/2)**2)
            b_vect = b_length*perp_vect_dir
            c_vect = a_vect+b_vect
            center_coords = c_vect
            final_pos = a_vect*2-c_vect 
            initial_pos = -c_vect
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
            vect_dir= [(values[0]-cp[k[0]])/dist,(values[1]-cp[k[1]])/dist]
            if direction == 'CW':
                arc_rotation_matrix = np.matrix([[0, -1],[1, 0]])
            elif direction =='CCW':
                arc_rotation_matrix = np.matrix([[0, 1],[-1, 0]])
            perp_vect_dir = np.array(vect_dir)*arc_rotation_matrix
            a_vect = np.array([(values[0]-cp[k[0]])/2.0,(values[1]-cp[k[1]])/2.0])
            b_length = math.sqrt(radius**2-(dist/2)**2)
            b_vect = b_length*perp_vect_dir
            c_vect = a_vect+b_vect
            center_coords = np.array(cp[k[:2]])+c_vect
            final_pos = np.array(cp[k[:2]])+a_vect*2-c_vect
            initial_pos = np.array(cp[k[:2]])

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

        if linearize:
            #Curved formed from straight lines
            final_pos = np.array(final_pos.tolist()).flatten()
            initial_pos = np.array(initial_pos.tolist()).flatten()
            final_angle = np.arctan2(final_pos[1],final_pos[0])
            initial_angle = np.arctan2(initial_pos[1],initial_pos[0])
            
            if direction == 'CW':
                angle_difference = 2*np.pi-(final_angle-initial_angle)%(2*np.pi)
            elif direction == 'CCW':
                angle_difference = (initial_angle-final_angle)%(-2*np.pi)

            step_range = [0, angle_difference]
            step_size = np.pi/16
            angle_step = np.arange(step_range[0],step_range[1]+np.sign(angle_difference)*step_size,np.sign(angle_difference)*step_size)
            
            segments = []
            for angle in angle_step:
                radius_vect = -c_vect
                radius_rotation_matrix = np.matrix([[math.cos(angle), -math.sin(angle)],
                                 [math.sin(angle), math.cos(angle)]])
                int_point = radius_vect*radius_rotation_matrix
                segments.append(int_point)
            
            for i in range(len(segments)-1):
                move_line = segments[i+1]-segments[i]
                self.move(*move_line.tolist()[0])
        else:
            #Standard output
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

    def round_rect(self, x, y, direction='CW', start='LL', radius=0, linearize=True):
        """ Trace a rectangle with the given width and height with rounded corners,
            note that starting point is not actually in corner of rectangle.

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
        radius : radius of the corners of the rectangle

        Examples
        --------
        >>> # trace a 10x10 clockwise square with radius of 3, starting in the lower left corner
        >>> g.round_rect(10, 10, radius=3)

        >>> # 1x5 counterclockwise rect with radius of 2 starting in the upper right corner
        >>> g.round_rect(1, 5, direction='CCW', start='UR', radius=2)
         
                                    ______________ 
                                   /              \
                                  /                \
        starts here for 'UL' - > |                  | <- starts here for 'UR'
                                 |                  |
        starts here for 'LL' - > |                  | <- starts here for 'LR'
                                  \                /
                                   \______________/

        """
        if direction == 'CW':
            if start.upper() == 'LL':
                self.move(y=y-2*radius)
                self.arc(x=radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
                self.arc(x=-radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=radius,direction='CW',radius=radius, linearize=linearize)
            elif start.upper() == 'UL':
                self.arc(x=radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
                self.arc(x=-radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)
            elif start.upper() == 'UR':
                self.move(y=-(y-2*radius))
                self.arc(x=-radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)
                self.arc(x=radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
            elif start.upper() == 'LR':
                self.arc(x=-radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)
                self.arc(x=radius,y=radius,direction='CW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=-radius,direction='CW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
        elif direction == 'CCW':
            if start.upper() == 'LL':
                self.arc(x=radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)
                self.arc(x=-radius,y=radius,direction='CCW',radius=radius, linearize=linearize)    
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
            elif start.upper() == 'UL':
                self.move(y=-(y-2*radius))
                self.arc(x=radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)
                self.arc(x=-radius,y=radius,direction='CCW',radius=radius, linearize=linearize)    
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
            elif start.upper() == 'UR':
                self.arc(x=-radius,y=radius,direction='CCW',radius=radius, linearize=linearize) 
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
                self.arc(x=radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=y-2*radius)   
            elif start.upper() == 'LR':
                self.move(y=y-2*radius)
                self.arc(x=-radius,y=radius,direction='CCW',radius=radius, linearize=linearize)    
                self.move(x=-(x-2*radius))
                self.arc(x=-radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(y=-(y-2*radius))
                self.arc(x=radius,y=-radius,direction='CCW',radius=radius, linearize=linearize)
                self.move(x=x-2*radius)
                self.arc(x=radius,y=radius,direction='CCW',radius=radius, linearize=linearize)

    def meander(self, x, y, spacing, start='LL', orientation='x', tail=False,
                minor_feed=None, color=(0,0,0,0.5)):
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
        color : hex string or rgb(a) string
            Specifies a color to be added to color history for viewing.

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
            self.move(**{major_name: (sign * major), 'color': color})
            if minor_feed != major_feed:
                self.feed(minor_feed)
            self.move(**{minor_name: spacing, 'color': color})
            if minor_feed != major_feed:
                self.feed(major_feed)
            sign = -1 * sign
        if tail is False:
            self.move(**{major_name: (sign * major), 'color': color})

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

    def spiral(self, end_diameter, spacing, feedrate, start='center', direction='CW', 
                step_angle = 0.1, start_diameter = 0, center_position=None):
        """ Performs an Archimedean spiral. Start by moving to the center of the spiral location
        then use the 'start' argument to specify a starting location (either center or edge).

        Parameters
        ----------
        end_diameter : float
            The outer diameter of the spiral.
        spacing : float
            The spacing between lines of the spiral.
        feedrate : float
            Feedrate is the speed of the nozzle relative to the substrate
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

        Examples

        >>> # start first spiral, outer diameter of 20, spacing of 1, feedrate of 8
        >>> g.spiral(20,1,8)

        >>> # move to second spiral location and do similar spiral but start at edge
        >>> g.spiral(20,1,8,start='edge',center_position=[50,0])

        >>> # move to third spiral location, this time starting at edge but printing CCW
        >>> g.spiral(20,1,8,start='edge',direction='CCW',center_position=[50,50])
        
        >>> # move to fourth spiral location, starting at center again but printing CCW
        >>> g.spiral(20,1,8,direction='CCW',center_position=[0,50])
        
        """
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

        for step in t[1:]:
            if (direction == 'CW' and start == 'center') or (direction == 'CCW' and start == 'edge'):
                x_move = -step*b*math.cos(step)+center_position[0]
            elif (direction == 'CCW' and start == 'center') or (direction == 'CW' and start == 'edge'):
                x_move = step*b*math.cos(step)+center_position[0]
            else:
                raise Exception("Must either choose 'CW' or 'CCW' for spiral direction.")
            y_move = step*b*math.sin(step)+center_position[1]
            self.move(x_move, y_move)

        #Set back to relative mode if it was previsously before command was called
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

    def purge_meander(self, x, y, spacing, volume_fraction, flowrate, start='LL', orientation='x',
            tail=False, minor_feed=None):
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
        """ Toggles (On/Off) Nordson Ultimus V Pressure Controllers.

        Parameters
        ----------
        com_port : int
            The com port to communicate over RS-232

        Examples
        --------
        >>> #Turn on pressure on com 3
        >>> g.toggle_pressure(3)

        """
        self.write('Call togglePress P{}'.format(com_port))
        if self.extruding[0] == com_port:
            self.extruding = [com_port, not self.extruding[1]]
        else:
            self.extruding = [com_port,True]

    def set_pressure(self, com_port, value):
        """ Sets pressure on Nordson Ultimus V Pressure Controllers.

        Parameters
        ----------
        com_port : int
            The com port to communicate over RS-232.
        value : float
            The pressure value to set.
        Examples
        --------
        >>> #Set pressure on com 3 to 50.
        >>> g.set_pressure(com_port=3, value=50)

        """
        self.write('Call setPress P{} Q{}'.format(com_port, value))

    def set_vac(self, com_port, value):
        """ Same as `set_pressure` method, but for vacuum.
        """
        self.write('Call setVac P{} Q{}'.format(com_port, value))

    def set_valve(self, num, value):
        """ Sets a digital output state (typically for valve).

        Parameters
        ----------
        num : int
            The com port to communicate over RS-232.
        value : bool
            On or off (1 or 0).
        Examples
        --------
        >>> #Turn on valve 2
        >>> g.set_valve(num=2, value=1)

        """
        self.write('$DO{}.0={}'.format(num, value))

    def omni_on(self, com_port):
        """ Opens the iris for the omnicure.

        Parameters
        ----------
        com_port : int
            The com port to communicate over RS-232

        Examples
        --------
        >>> #Turn on omnicure on com 3.
        >>> g.omni_on(3)

        """
        self.write('Call omniOn P{}'.format(com_port))

    def omni_off(self, com_port):
        """ Opposite to omni_on.
        """
        self.write('Call omniOff P{}'.format(com_port))

    def omni_intensity(self, com_port, value, cal=False):
        """ Sets the intensity of the omnicure.

        Parameters
        ----------
        com_port : int
            The com port to communicate over RS-232.
        value : float
            The intensity value to set.
        cal : bool
            Whether the omnicure is calibrated or not.
        Examples
        --------
        >>> #Set omnicure intensity on com 3 to 50%.
        >>> g.omni_intensity(com_port=3, value=50)

        """

        if cal:
            command = 'SIR{:.2f}'.format(value)
            data = self.calc_CRC8(command)
            self.write('$strtask4="{}"'.format(data))
        else:
            command = 'SIL{:.0f}'.format(value)
            data = self.calc_CRC8(command)
            self.write('$strtask4="{}"'.format(data))
        self.write('Call omniSetInt P{}'.format(com_port))

    def set_alicat_pressure(self,com_port,value):
        """ Same as `set_pressure` method, but for Alicat controller.
        """
        self.write('Call setAlicatPress P{} Q{}'.format(com_port, value))

    def calc_CRC8(self,data):
        CRC8 = 0
        for letter in list(bytearray(data, encoding='utf-8')):
            for i in range(8):
                if (letter^CRC8)&0x01:
                    CRC8 ^= 0x18
                    CRC8 >>= 1
                    CRC8 |= 0x80
                else:
                    CRC8 >>= 1
                letter >>= 1
        return data +'{:02X}'.format(CRC8)

    def gen_geometry(self,outfile,filament_diameter=0.8,cut_point=None,preview=False,color_incl=None):
        """ Creates an openscad file to create a CAD model from the print path.
        
        Parameters
        ----------
        outfile : str
            Location to save the generated .scad file
        filament_diameter : float (default: 0.8)
            The com port to communicate over RS-232.
        cut_point : int (default: None)
            Stop generating cad model part way through the path
        preview : bool (default: False)
            Show matplotlib preview of the part to be generated.
            Note that cut_point will affect the preview.
        color_incl : str (default: None)
            Used to export a single color when it is included in the code
            design. Useful for exporting mutlimaterial parts as different
            cad models.
        Examples
        --------
        >>> #Write geometry to 'test.scad'
        >>> g.gen_geometry('test.scad')

        """
        import solid as sld
        from solid import utils as sldutils

        # Matplotlib setup for preview
        import matplotlib.cm as cm
        from mpl_toolkits.mplot3d import Axes3D
        import matplotlib.pyplot as plt
        fig = plt.figure()
        ax = fig.gca(projection='3d')

        def circle(radius,num_points=10):
            circle_pts = []
            for i in range(2 * num_points):
                angle = math.radians(360 / (2 * num_points) * i)
                circle_pts.append(sldutils.Point3(radius * math.cos(angle), radius * math.sin(angle), 0))
            return circle_pts
        
        # SolidPython setup for geometry creation
        extruded = 0
        filament_cross = circle(radius=filament_diameter/2)

        extruding_hist = dict(self.extruding_history)
        position_hist = np.array(self.position_history)

        #Stepping through all moves after initial position
        extruding_state = False
        for index, (pos, color) in enumerate(zip(self.position_history[1:cut_point],self.color_history[1:cut_point]),1):
            sys.stdout.write('\r')
            sys.stdout.write("Exporting model: {:.0f}%".format(index/len(self.position_history[1:])*100))
            sys.stdout.flush()
            #print("{}/{}".format(index,len(self.position_history[1:])))
            if index in extruding_hist:
                extruding_state =  extruding_hist[index][1]

            if extruding_state and ((color == color_incl) or (color_incl is None)):
                X, Y, Z = position_hist[index-1:index+1, 0], position_hist[index-1:index+1, 1], position_hist[index-1:index+1, 2]
                # Plot to matplotlb
                if color_incl is not None:
                    ax.plot(X, Y, Z,color_incl)
                else:
                    ax.plot(X, Y, Z,'b')
                # Add geometry to part
                extruded += sldutils.extrude_along_path(shape_pts=filament_cross, path_pts=[sldutils.Point3(*position_hist[index-1]),sldutils.Point3(*position_hist[index])])
                extruded += sld.translate(position_hist[index-1])(sld.sphere(r=filament_diameter/2,segments=20))
                extruded += sld.translate(position_hist[index])(sld.sphere(r=filament_diameter/2,segments=20))
                
        # Export geometry to file
        file_out = os.path.join(os.curdir, '{}.scad'.format(outfile))
        print("\nSCAD file written to: \n%(file_out)s" % vars())
        sld.scad_render_to_file(extruded, file_out, include_orig_code=False)

        if preview:
            # Display Geometry for matplotlib
            X, Y, Z = position_hist[:, 0], position_hist[:, 1], position_hist[:, 2]

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
            scaling = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz']); ax.auto_scale_xyz(*[[np.min(scaling), np.max(scaling)]]*3)
            plt.show()

    # ROS3DA Functions  #######################################################


    def line_frequency(self,freq,padding,length,com_port,pressure,travel_feed):
        """ Prints a line with varying on/off frequency.

        Parameters
        ----------
        frequency : float
            The length to move in x in one half cycle
        """

        # Switch to relative if in absolute, but keep track of state
        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        # Use velocity on, required for switching like this
        self.write("VELOCITY ON")

        print_height = np.copy(self._current_position['z'])
        print_feed = np.copy(self.speed)

        self.set_pressure(com_port,pressure)
        for f in freq:
            # freq is in hz, ie 1/s. Thus dist = (m/s)/(1/s) = m
            dist = print_feed/f
            switch_points = np.arange(length+dist,step=dist)
            if len(switch_points)%2:
                switch_points = switch_points[:-1]
            for point in switch_points:
                self.toggle_pressure(com_port)
                self.move(x=dist)
                
            #Move to push into substrate
            self.move(z=-print_height)
            self.feed(travel_feed)
            self.move(z=print_height+5)

            if f != freq[-1]:
                self.move(x=-len(switch_points)*dist,y=padding)
                self.move(z=-5)
                self.feed(print_feed)

        # Switch back to velocity off
        self.write("VELOCITY OFF")
        # Switch back to absolute if it was in absolute
        if was_absolute:
            self.absolute()

        return [length,padding*(len(freq)-1)]

    def line_width(self,padding,width,com_port,pressures,spacing,travel_feed):
        """ Prints meanders of varying spacing with different pressures.

        Parameters
        ----------
        frequency : float
            The length to move in x in one half cycle
        """
        # Switch to relative if in absolute, but keep track of state
        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        print_height = np.copy(self._current_position['z'])
        print_feed = np.copy(self.speed)
        
        for pressure in pressures:
            direction = 1
            self.set_pressure(com_port,pressure)
            self.toggle_pressure(com_port)
            for space in spacing:
                #self.toggle_pressure(com_port)
                self.move(y=direction*width)
                self.move(space)
                if space == spacing[-1]:
                    self.move(y=-direction*width)
                #self.toggle_pressure(com_port)
                direction *= -1
            self.toggle_pressure(com_port)
            self.feed(travel_feed)
            self.move(z=5)
            if pressure != pressures[-1]:
                self.move(x=-np.sum(spacing),y=width+padding)
                self.move(z=-5)
                self.feed(print_feed)

        # Switch back to absolute if it was in absolute
        if was_absolute:
            self.absolute()

        return [np.sum(spacing)*2-spacing[-1],len(pressures)*width + (len(pressures)-1)*padding]

    def line_span(self,padding,dwell,distances,com_port,pressure,travel_feed):
        """ Prints meanders of varying spacing with different pressures.

        Parameters
        ----------
        frequency : float
            The length to move in x in one half cycle
        """
        # Switch to relative if in absolute, but keep track of state
        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        print_height = np.copy(self._current_position['z'])
        print_feed = np.copy(self.speed)

        for dist in distances:
            self.toggle_pressure(com_port)
            self.dwell(dwell)
            self.feed(print_feed*dist/distances[0])
            self.move(y=dist)
            self.dwell(dwell)
            self.toggle_pressure(com_port)

            self.move(z=-print_height)
            self.feed(travel_feed)
            self.move(z=print_height+5)
            if dist != distances[-1]:
                self.move(x=padding,y=-dist)
                self.move(z=-5)
                self.feed(print_feed)

        # Switch back to absolute if it was in absolute
        if was_absolute:
            self.absolute()

        return [padding*(len(distances)-1),np.max(distances)]


    def line_crossing(self,dwell,feeds,length,com_port,pressure,travel_feed):
        """ Prints meanders of varying spacing with different pressures.

        Parameters
        ----------
        frequency : float
            The length to move in x in one half cycle
        """
        # Switch to relative if in absolute, but keep track of state
        was_absolute = True
        if not self.is_relative:
            self.relative()
        else:
            was_absolute = False

        print_height = np.copy(self._current_position['z'])

        self.set_pressure(com_port,pressure)
        self.toggle_pressure(com_port)
        self.dwell(dwell)
        self.move(x=length)
        self.dwell(dwell)
        self.toggle_pressure(com_port)
        self.move(z=-print_height)
        self.feed(travel_feed)
        self.move(z=print_height+5)

        spacing = length/(len(feeds)+1)
        self.move(x=-spacing,y=8)
        for feed in feeds:
            self.move(z=-(print_height+5))
            self.feed(feed)
            self.move(y=-16)
            if feed != feeds[-1]:
                self.feed(travel_feed)
                self.move(z=print_height+5)
                self.move(x=-spacing,y=16)

        self.feed(travel_feed)
        self.move(z=print_height+5)

        # Switch back to absolute if it was in absolute
        if was_absolute:
            self.absolute()

        return length

    def export_APE(self):
        """ Exports a list of dictionaries describing extrusion moves in a
        format compatible with APE.

        Examples
        --------
        >>> #Write print geometry
        >>> geometry_def = g.meander()

        """
        extruding_hist = dict(self.extruding_history)
        position_hist = self.position_history
        cut_ranges=[*extruding_hist][1:]
        final_coords = []
        for i in range(0,len(cut_ranges),2):
            final_coords.append(position_hist[cut_ranges[i]-1:cut_ranges[i+1]])
        final_coords_dict = []
        for i in final_coords:
            keys = ['X','Y','Z']
            final_coords_dict.append([dict(zip(keys, l)) for l in i ])
        return final_coords_dict

    # Public Interface  #######################################################

    def view(self, backend='matplotlib', outfile=None, hide_travel=False,color_on=True, nozzle_cam=False,
             fast_forward = 3, framerate = 60, nozzle_dims=[1.0,20.0], 
             substrate_dims=[0.0,0.0,-1.0,300,1,300], scene_dims = [720,720]):
        """ View the generated Gcode.

        Parameters
        ----------
        backend : str (default: 'matplotlib')
            The plotting backend to use, one of 'matplotlib' or 'mayavi'.
            'matplotlib2d' has been addded to better visualize mixing.
            'vpython' has been added to generate printing animations
            for debugging.
        outfile : str (default: 'None')
            When using the 'matplotlib' backend,
            an image of the output will be save to the location specified
            here.
        color_on : bool (default: 'False')
            When using the 'matplotlib' or 'matplotlib2d' backend,
            the generated image will display the color associated
            with the g.move command. This was primarily used for mixing
            nozzle debugging.
        nozzle_cam : bool (default: 'False')
            When using the 'vpython' backend and nozzle_cam is set to 
            True, the camera will remained centered on the tip of the 
            nozzle during the animation.
        fast_forward : int (default: 1)
            When using the 'vpython' backend, the animation can be
            sped up by the factor specified in the fast_forward 
            parameter.
        nozzle_dims : list (default: [1.0,20.0])
            When using the 'vpython' backend, the dimensions of the 
            nozzle can be specified using a list in the format:
            [nozzle_diameter, nozzle_length].
        substrate_dims: list (default: [0.0,0.0,-0.5,100,1,100])
            When using the 'vpython' backend, the dimensions of the 
            planar substrate can be specified using a list in the 
            format: [x, y, z, length, height, width].
        scene_dims: list (default: [720,720])
            When using the 'vpython' bakcend, the dimensions of the
            viewing window can be specified using a list in the 
            format: [width, height]

        """
        import matplotlib.cm as cm
        from mpl_toolkits.mplot3d import Axes3D
        import matplotlib.pyplot as plt
        history = np.array(self.position_history)

        if backend == 'matplotlib':
            fig = plt.figure()
            ax = fig.add_subplot(projection='3d')

            extruding_hist = dict(self.extruding_history)
            #Stepping through all moves after initial position
            extruding_state = False
            for index, (pos, color) in enumerate(zip(history[1:],self.color_history[1:]),1):
                if index in extruding_hist:
                    extruding_state =  extruding_hist[index][1]

                X, Y, Z = history[index-1:index+1, 0], history[index-1:index+1, 1], history[index-1:index+1, 2]

                if extruding_state:
                    if color_on:
                        # ax.plot(X, Y, Z,color = cm.gray(self.color_history[index])[:-1])
                        print(self.color_history[index])
                        ax.plot(X, Y, Z,color = self.color_history[index])
                    else:
                        ax.plot(X, Y, Z,'b')
                else:
                    if not hide_travel:
                        ax.plot(X,Y,Z,'k--',linewidth=0.5)

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
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")

            if outfile == None:
                plt.show()
            else:
                plt.savefig(outfile,dpi=500)

        elif backend == 'mayavi':
            from mayavi import mlab
            mlab.plot3d(history[:, 0], history[:, 1], history[:, 2])

        elif backend == 'vpython':
            import vpython as vp
            import copy
            
            #Scene setup
            vp.scene.width = scene_dims[0]
            vp.scene.height = scene_dims[1]
            vp.scene.center = vp.vec(0,0,0) 
            vp.scene.forward = vp.vec(-1,-1,-1) 
            vp.scene.background = vp.vec(1,1,1)

            position_hist = history
            speed_hist = dict(self.speed_history)
            extruding_hist = dict(self.extruding_history)
            extruding_state = False
            printheads = np.unique([i[1][0] for i in self.extruding_history][1:])
            vpython_colors = [vp.color.red,vp.color.blue,vp.color.green,vp.color.cyan,vp.color.yellow,vp.color.magenta,vp.color.orange]
            filament_color = dict(zip(printheads,vpython_colors[:len(printheads)]))

            #Swap Y & Z axis for new coordinate system
            position_hist[:,[1,2]] = position_hist[:,[2,1]]
            #Swap Z direction
            position_hist[:,2] *= -1

            #Check all values are available for animation
            if 0 in speed_hist.values():
                raise ValueError('Cannot specify 0 for feedrate')

            class Printhead(object):
                def __init__(self, nozzle_diameter, nozzle_length, start_location=vp.vec(0,0,0), start_orientation=vp.vec(0,1,0)):
                    #Record initialized position as current position
                    self.current_position = start_location
                    self.nozzle_length = nozzle_length
                    self.nozzle_diameter = nozzle_diameter

                    #Create a cylinder to act as the nozzle
                    self.head = vp.cylinder(pos=start_location,
                                        axis=nozzle_length*start_orientation, 
                                        radius=nozzle_diameter/2, 
                                        texture=vp.textures.metal)

                    #Create trail for filament
                    self.tail = []
                    self.previous_head_position = copy.copy(self.head.pos)
                    self.make_trail = False
                    
                    #Create Luer lock fitting
                    cyl_outline = np.array([[0.2,0],
                                   [1.2,1.4],
                                   [1.2,5.15],
                                   [2.4,8.7],
                                   [2.6,15.6],
                                   [2.4,15.6],
                                   [2.2,8.7],
                                   [1.0,5.15],
                                   [1.0,1.4],
                                   [0,0],
                                   [0.2,0]])
                    fins_outline_r = np.array([[1.2,2.9],
                                   [3.0,3.7],
                                   [3.25,15.6],
                                   [2.6,15.6],
                                   [2.4,8.7],
                                   [1.2,5.15],
                                   [1.2,2.9]])
                    fins_outline_l = np.array([[-1.2,2.9],
                                   [-3.0,3.7],
                                   [-3.25,15.6],
                                   [-2.6,15.6],
                                   [-2.4,8.7],
                                   [-1.2,5.15],
                                   [-1.2,2.9]])
                    cyl_outline[:,1] += nozzle_length
                    fins_outline_r[:,1] += nozzle_length
                    fins_outline_l[:,1] += nozzle_length
                    cylpath = vp.paths.circle(radius=0.72/2)
                    left_fin = vp.extrusion(path=[vp.vec(0,0,-0.1),vp.vec(0,0,0.1)],shape=fins_outline_r.tolist(),color=vp.color.blue,opacity=0.7,shininess=0.1)
                    right_fin =vp.extrusion(path=[vp.vec(0,0,-0.1),vp.vec(0,0,0.1)],shape=fins_outline_l.tolist(),color=vp.color.blue,opacity=0.7,shininess=0.1)
                    luer_body = vp.extrusion(path=cylpath, shape=cyl_outline.tolist(), color=vp.color.blue,opacity=0.7,shininess=0.1)
                    luer_fitting = vp.compound([luer_body, right_fin, left_fin])

                    #Create Nordson Barrel
                    #Barrel_outline exterior
                    first_part = [[5.25,0]]
                    barrel_curve = np.array([[ 0.        , 0.        ],
                                    [ 0.01538957,  0.19554308],
                                    [ 0.06117935,  0.38627124],
                                    [ 0.13624184,  0.56748812],
                                    [ 0.23872876,  0.73473157],
                                    [ 0.36611652,  0.88388348],
                                    [ 0.9775778 ,  1.82249027],
                                    [ 1.46951498,  2.73798544],
                                    [ 1.82981493,  3.60782647],
                                    [ 2.04960588,  4.41059499],
                                    [ 2.12347584,  5.12652416]])
                    barrel_curve *= 1.5
                    barrel_curve[:,0] += 5.25
                    barrel_curve[:,1] += 8.25
                    last_part = [[9.2,17.0],
                                 [9.2,80]]

                    barrel_outline = np.append(first_part,barrel_curve,axis=0)
                    barrel_outline = np.append(barrel_outline,last_part,axis=0)
                    barrel_outline[:,0] -= 1
                   
                   #Create interior surface
                    barrel_outline_inter = np.copy(np.flip(barrel_outline,axis=0))
                    barrel_outline_inter[:,0] -= 2.5
                    barrel_outline = np.append(barrel_outline,barrel_outline_inter,axis=0)
                    barrel_outline = np.append(barrel_outline,[[4.25,0]],axis=0)
                    barrel_outline[:,1] += 13 + nozzle_length

                    barrelpath = vp.paths.circle(radius=2.0/2)
                    barrel = vp.extrusion(path=barrelpath, shape=barrel_outline.tolist(), color=vp.color.gray(0.8),opacity=1.0,shininess=0.1)

                    #Combine into single head
                    self.body = vp.compound([barrel,luer_fitting],pos=start_location+vp.vec(0,nozzle_length+46.5,0))

                def abs_move(self, endpoint, feed=2.0,print_line=True,tail_color = None):
                    move_length = (endpoint - self.current_position).mag
                    time_to_move = move_length/(feed*fast_forward)
                    total_frames = round(time_to_move*framerate)

                    #Create linspace of points between beginning and end
                    inter_points = np.array([np.linspace(i,j,total_frames) for i,j in zip([self.current_position.x,self.current_position.y,self.current_position.z],[endpoint.x,endpoint.y,endpoint.z])])

                    for inter_move in np.transpose(inter_points): 
                        vp.rate(framerate)
                        self.head.pos.x = self.body.pos.x = inter_move[0]
                        self.head.pos.z = self.body.pos.z = inter_move[2]
                        self.head.pos.y = inter_move[1]
                        self.body.pos.y = inter_move[1]+self.nozzle_length+46.5
                        
                        if self.make_trail and print_line :  
                            if (self.previous_head_position.x != self.head.pos.x) or (self.previous_head_position.y != self.head.pos.y) or (self.previous_head_position.z != self.head.pos.z):  
                                self.tail[-1].append(pos=vp.vec(self.head.pos.x,self.head.pos.y-self.nozzle_diameter/2,self.head.pos.z))
                        elif not self.make_trail and print_line:
                            vp.sphere(pos=vp.vec(self.head.pos.x,self.head.pos.y-self.nozzle_diameter/2,self.head.pos.z),color=tail_color,radius=self.nozzle_diameter/2)
                            self.tail.append(vp.curve(pos=vp.vec(self.head.pos.x,self.head.pos.y-self.nozzle_diameter/2,self.head.pos.z),color=tail_color,radius=self.nozzle_diameter/2))
                        self.make_trail = print_line

                        self.previous_head_position = copy.copy(self.head.pos)

                        #Track tip of nozzle with camera if nozzle_cam mode is on
                        if nozzle_cam:
                            vp.scene.center = self.head.pos
        
                    #Set endpoint as current position
                    self.current_position = endpoint

            def run():
                #Stepping through all moves after initial position
                extruding_state = False
                for count, (pos, color) in enumerate(zip(position_hist[1:],self.color_history[1:]),1):
                    X, Y, Z = pos
                    if count in speed_hist:
                        t_speed = speed_hist[count]
                    if count in extruding_hist:
                        extruding_state =  extruding_hist[count][1]
                        t_color = filament_color[extruding_hist[count][0]] if extruding_hist[count][0] != None else vp.color.black
                    self.head.abs_move(vp.vec(*pos),feed=t_speed,print_line=extruding_state,tail_color=t_color)

            self.head = Printhead(nozzle_diameter=nozzle_dims[0],nozzle_length=nozzle_dims[1], start_location=vp.vec(*position_hist[0]))
            vp.box(pos=vp.vec(substrate_dims[0],substrate_dims[2],substrate_dims[1]),length=substrate_dims[3], height=substrate_dims[4], width=substrate_dims[5],color=vp.color.gray(0.8))
            vp.scene.waitfor('click')
            run()

        else:
            raise Exception("Invalid plotting backend! Choose one of mayavi or matplotlib or matplotlib2d or vpython.")

    def write(self, statement_in, resp_needed=False):
        if self.print_lines:
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
                    from .printer import Printer
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
        if 'b' in self.out_fd.mode:  # encode the string to binary if needed
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
        if (len(self.extruding_history) == 0
            or self.extruding_history[-1][1] != self.extruding):
            self.extruding_history.append((len_history - 1, self.extruding))

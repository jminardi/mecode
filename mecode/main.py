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
* *Email:* jminardi@seas.harvard.edu

This software was developed by the Lewis Lab at Harvard University.

"""

import math
import os
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
                 aerotech_include=True, cal_data=None, cal_axis='A',
                 direct_write=False, printer_host='localhost',
                 printer_port=8000, two_way_comm=True, extrude = False, 
                 filament_diameter = 1.75, layer_height = 0.22, 
                 extrusion_width = 0.4, extrusion_multiplier = 1):
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
        cal_data : Nx3 array or None (default: None)
            Numpy array representing calibration data. The array should be a
            series of x, y, z points, where z is the delta to adjust for the
            given x, y.
        cal_axis : str (default: 'A')
            The axis that the calibration deltas should apply to.
        direct_write : bool (default: False)
            If True a socket is opened to the printer and the GCode is sent
            directly over.
        printer_host : str (default: 'localhost')
            Hostname of the printer, only used if `direct_write` is True.
        printer_port : int (default: 8000)
            Port of the printer, only used if `direct_write` is True.
        two_way_comm : bool (default: True)
            If True, mecode waits for a response after every line of GCode is
            sent over the socket. The response is returned by the `write`
            method. Only applies if `direct_write` is True.
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
        self.cal_axis = cal_axis
        self.cal_data = cal_data

        self.current_position = defaultdict(float)
        self.is_relative = True
                
        self.extrude = extrude
        self.filament_diameter = filament_diameter
        self.layer_height = layer_height
        self.extrusion_width = extrusion_width
        self.extrusion_multiplier = extrusion_multiplier
                
        self.position_history = [(0, 0, 0)]
        self.speed = 0
        self.speed_history = []

        self.direct_write = direct_write
        self.printer_host = printer_host
        self.printer_port = printer_port
        self.two_way_comm = two_way_comm
        self._socket = None

        self.setup()

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

    def set_home(self, x=None, y=None, **kwargs):
        """ Set the current position to the given position without moving.

        Example
        -------
        >>> # set the current position to X=0, Y=0
        >>> g.set_home(0, 0)

        """
        args = self._format_args(x, y, kwargs)
        self.write('G92 ' + args)

        self._update_current_position(mode='absolute', x=x, y=y, **kwargs)

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
        self.write('F{}'.format(rate))
        self.speed = rate

    def dwell(self, time):
        """ Pause code executions for the given amount of time.

        Parameters
        ----------
        time : float
            Time in seconds to pause code execution.

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

    def teardown(self):
        """ Close the outfile file after writing the footer if opened. This
        method must be called once after all commands.

        """
        if self.out_fd is not None:
            if self.aerotech_include is True:
                with open(os.path.join(HERE, 'footer.txt')) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x) for x in lines]
                    self.out_fd.writelines(lines)
            if self.footer is not None:
                with open(self.footer) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x) for x in lines]
                    self.out_fd.writelines(lines)
                    self.out_fd.write(encode2To3('\n'))
            self.out_fd.close()
        if self._socket is not None:
            self._socket.close()

    def home(self):
        """ Move the tool head to the home position (X=0, Y=0).
        """
        self.abs_move(x=0, y=0)

    def move(self, x=None, y=None, **kwargs):
        """ Move the tool head to the given position. This method operates in
        relative mode unless a manual call to `absolute` was given previously.
        If an absolute movement is desired, the `abs_move` method is
        recommended instead.

        Examples
        --------
        >>> # move the tool head 10 mm in x and 10 mm in y
        >>> g.move(x=10, y=10)
        >>> # the x and y keywords may be omitted:
        >>> g.move(10, 10)

        >>> # move the A axis up 20 mm
        >>> g.move(A=20)

        """
        
        if self.cal_data is not None:
            cal_axis = self.cal_axis
            x_, y_ = self.current_position['x'], self.current_position['y']
            if self.is_relative:
                if x is not None:
                    x_ = x_ + x
                if y is not None:
                    y_ = y_ + y
            else:
                if x is not None:
                    x_ = x
                if y is not None:
                    y_ = y
            desired_position = self.interpolate(x_, y_)
            x_current = self.current_position['x']
            y_current = self.current_position['y']
            current_interp_pos = self.interpolate(x_current, y_current)
            delta = desired_position - current_interp_pos
            if cal_axis in kwargs:
                kwargs[cal_axis] += delta
            else:
                kwargs[cal_axis] = delta
                
        if self.extrude is True:
            area = self.layer_height*(self.extrusion_width-self.layer_height) + 3.14159*(self.layer_height/2)**2
            if x is None:
                x=0
            if y is None:
                y=0
            if self.is_relative is not True:
                current_x_pos = self.current_position['x']
                current_y_pos = self.current_position['y']
                x_distance = abs(x-current_x_pos)
                y_distance = abs(y-current_y_pos)
                current_extruder_position = self.current_position['E']
            else:
                x_distance = x
                y_distance = y
                current_extruder_position = 0
            line_length = math.sqrt(x_distance**2 + y_distance**2)
            volume = line_length*area
            filament_length = ((4*volume)/(3.14149*self.filament_diameter**2))*self.extrusion_multiplier    
            
        if self.extrude is True:
            kwargs['E'] = filament_length + current_extruder_position
            
        self._update_current_position(x=x, y=y, **kwargs)
        

        args = self._format_args(x, y, kwargs)
        self.write('G1 ' + args)
    
    def retract(self, retraction):
        self.extrude = False
        self.move(E = -retraction)
        self.extrude = True
        
    def abs_move(self, x=None, y=None, **kwargs):
        """ Same as `move` method, but positions are interpreted as absolute.
        """
        if self.is_relative:
            self.absolute()
            self.move(x=x, y=y, **kwargs)
            self.relative()
        else:
            self.move(x=x, y=y, **kwargs)

    def arc(self, direction='CW', radius='auto', helix_dim=None, helix_len=0,
            **kwargs):
        """ Arc to the given point with the given radius and in the given
        direction. If helix_dim and helix_len are specified then the tool head
        will also perform a linear movement through the given dimension while
        completing the arc.

        Parameters
        ----------
        points : floats
            Must specify two points as kwargs, e.g. X=5, Y=5
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
        msg = 'Must specify point with 2 dimensions as keywords, e.g. X=0, Y=10'
        if len(kwargs) != 2:
            raise RuntimeError(msg)
        dimensions = [k.lower() for k in kwargs.keys()]
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

        if direction == 'CW':
            command = 'G2'
        elif direction == 'CCW':
            command = 'G3'

        values = [v for v in kwargs.values()]
        if self.is_relative:
            dist = math.sqrt(values[0] ** 2 + values[1] ** 2)
        else:
            k = [ky for ky in kwargs.keys()]
            cp = self.current_position
            dist = math.sqrt(
                (cp[k[0]] - values[0]) ** 2 + (cp[k[1]] - values[1]) ** 2
            )
        if radius == 'auto':
            radius = dist / 2.0
        elif radius < dist / 2.0:
            msg = 'Radius {} to small for distance {}'.format(radius, dist)
            raise RuntimeError(msg)

        if axis is not None:
            self.write('G16 X Y {}'.format(axis))  # coordinate axis assignment
        self.write(plane_selector)
        args = ' '.join([(k.upper() + str(v)) for
                         k, v in sorted(kwargs.items(), key=lambda x: x[0])])
        if helix_dim is None:
            self.write('{} {} R{}'.format(command, args, radius))
        else:
            self.write('{} {} R{} G1 {}{}'.format(command, args, radius,
                                                  helix_dim.upper(), helix_len))
            kwargs[helix_dim] = helix_len

        self._update_current_position(**kwargs)

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

    def meander(self, x, y, spacing, start='LL', orientation='x', tail=False):
        """ Infill a rectangle with a square wave meandering pattern. If the
        relevant dimension is not a multiple of the spacing, the spacing will
        be tweaked to ensure the dimensions work out.

        Parameters
        ----------
        x : float
            The width of the rectangle in the x dimension.
        y : float
            The heigh of the rectangle in the y dimension.
        spacing : float
            The space between parallel meander lines.
        start : str (either 'LL', 'UL', 'LR', 'UR') (default: 'LL')
            The start of the meander -  L/U = lower/upper, L/R = left/right
            This assumes an origin in the lower left.
        orientation : str ('x' or 'y') (default: 'x')

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

        if minor > 0:
            passes = math.ceil(minor / spacing)
        else:
            passes = abs(math.floor(minor / spacing))
        actual_spacing = minor / passes
        if abs(actual_spacing) != spacing:
            msg = ';WARNING! meander spacing updated from {} to {}'
            self.write(msg.format(spacing, actual_spacing))
        spacing = actual_spacing
        sign = 1
        self.relative()
        for _ in range(int(passes)):
            self.move(**{major_name: (sign * major)})
            self.move(**{minor_name: spacing})
            sign = -1 * sign
        if tail is False:
            self.move(**{major_name: (sign * major)})

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

    def align_nozzle(self, nozzle, floor=-72, deltafast=1, deltaslow=0.1,
                     start=-15):
        if nozzle == 'A':
            nozzle = 1
        elif nozzle == 'B':
            nozzle = 2
        elif nozzle == 'C':
            nozzle = 3
        elif nozzle == 'D':
            nozzle = 4
        elif nozzle == 'profilometer':
            nozzle = 5
        else:
            raise RuntimeError('invalid nozzle: {}'.format(nozzle))
        arg = 'Call alignNozzle Q{} R{} L{} I{} J{}'
        self.write(arg.format(start, deltaslow, nozzle, floor, deltafast))

    def align_zero_nozzle(self, nozzle, floor=-72, deltafast=1, deltaslow=0.1,
                          start=-15):
        if nozzle == 'A':
            nozzle = 1
        elif nozzle == 'B':
            nozzle = 2
        elif nozzle == 'C':
            nozzle = 3
        elif nozzle == 'D':
            nozzle = 4
        elif nozzle == 'profilometer':
            nozzle = 5
        else:
            raise RuntimeError('invalid nozzle: {}'.format(nozzle))
        arg = 'Call alignZeroNozzle Q{} R{} L{} I{} J{}'
        self.write(arg.format(start, deltaslow, nozzle, floor, deltafast))

    def set_pressure(self, com_port, value):
        self.write('Call setPress P{} Q{}'.format(com_port, value))

    def set_valve(self, num, value):
        self.write('$DO{}.0={}'.format(num, value))

    def save_alignment(self, nozzle='A'):
        if nozzle == 'A':
            nozzle = 1
        elif nozzle == 'B':
            nozzle = 2
        elif nozzle == 'C':
            nozzle = 3
        elif nozzle == 'D':
            nozzle = 4
        elif nozzle == 'all':
            self.write('Call save_value Q1')
            self.write('Call save_value Q2')
            self.write('Call save_value Q3')
            nozzle = 4
        self.write('Call save_value Q{}'.format(nozzle))

    # Public Interface  #######################################################

    def interpolate(self, x, y):
        from scipy.interpolate import griddata
        cal_data = self.cal_data
        delta = griddata((cal_data[:, 0], cal_data[:, 1]), cal_data[:, 2],
                         (x, y), method='linear', fill_value=0)
        return delta

    def show_interpolation_surface(self, interpolate=True):
        from mpl_toolkits.mplot3d import Axes3D  # noqa
        import matplotlib.pyplot as plt
        import numpy as np
        ax = plt.figure().gca(projection='3d')
        d = self.cal_data
        ax.scatter(d[:, 0], d[:, 1], d[:, 2])
        if interpolate:
            x_min, x_max = d[:, 0].min(), d[:, 0].max()
            y_min, y_max = d[:, 1].min(), d[:, 1].max()
            xx, yy = np.meshgrid(np.linspace(x_min, x_max, 50),
                                 np.linspace(y_min, y_max, 50))
            xxr, yyr = xx.reshape(-1), yy.reshape(-1)
            zz = self.interpolate(xxr, yyr)
            ax.scatter(xxr, yyr, zz, color='red')
        plt.show()

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
            ax.plot(history[:, 0], history[:, 1], history[:, 2])
            plt.show()
        elif backend == 'mayavi':
            from mayavi import mlab
            mlab.plot3d(history[:, 0], history[:, 1], history[:, 2])
        else:
            raise Exception("Invalid plotting backend! Choose one of mayavi or matplotlib.")

    def write(self, statement_in):
        if self.print_lines:
            print(statement_in)
        statement = encode2To3(statement_in + '\n')
        if self.out_fd is not None:
            self.out_fd.write(statement)
        if self.direct_write is True:
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

    # Private Interface  ######################################################
    def _write_header(self):
        outfile = self.outfile
        if outfile is not None or self.out_fd is not None:
            if self.out_fd is None:  # open it if it is a path
                self.out_fd = open(outfile, 'w+')
            if self.aerotech_include is True:
                with open(os.path.join(HERE, 'header.txt')) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x) for x in lines]
                    self.out_fd.writelines(lines)
                    self.out_fd.write(encode2To3('\n'))
            if self.header is not None:
                with open(self.header) as fd:
                    lines = fd.readlines()
                    lines = [encode2To3(x) for x in lines]
                    self.out_fd.writelines(lines)
                    self.out_fd.write(encode2To3('\n'))

    def _format_args(self, x, y, kwargs):
        args = []
        if x is not None:
            args.append('X{0:f}'.format(x))
        if y is not None:
            args.append('Y{0:f}'.format(y))
        args += ['{0}{1:f}'.format(k, v) for k, v in kwargs.items()]
        args = ' '.join(args)
        return args

    def _update_current_position(self, mode='auto', x=None, y=None, **kwargs):
        if mode == 'auto':
            mode = 'relative' if self.is_relative else 'absolute'

        if mode == 'relative':
            if x is not None:
                self.current_position['x'] += x
            if y is not None:
                self.current_position['y'] += y
            for dimention, delta in kwargs.items():
                self.current_position[dimention] += delta
        else:
            if x is not None:
                self.current_position['x'] = x
            if y is not None:
                self.current_position['y'] = y
            for dimention, delta in kwargs.items():
                self.current_position[dimention] = delta

        x = self.current_position['x']
        y = self.current_position['y']
        z = self.current_position['z']
        self.position_history.append((x, y, z))

        len_history = len(self.position_history)
        if len(self.speed_history) == 0 or self.speed_history[-1][1] != self.speed:
            self.speed_history.append((len_history - 1, self.speed))


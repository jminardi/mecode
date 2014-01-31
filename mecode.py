"""
mecode is a collection of functions desiged to simplify generation of GCode.

Relative movements are assumed, unless stated in the function name. Any
function that uses absolute mode always resets back to relative.

"""

import math


###############################################################################
### GCode Aliases
###############################################################################

def set_home(x=0, y=0, **kwargs):
    args = _format_args(x, y, kwargs)
    write('G92 ' + args)


def reset_home():
    write('G92.1')


def move(x=None, y=None, **kwargs):
    args = _format_args(x, y, kwargs)
    write('G1 ' + args)


def feed(rate):
    write('F{}'.format(rate))


def dwell(time):
    write('G4 P{}'.format(time))


###############################################################################
### Composed Functions
###############################################################################

def setup():
    """ Set the environment into a consistent state to start off.
    """
    write('G91')  # start off in relative mode.


def home():
    write('G90')
    write('G1 X0 Y0')
    write('G91')


def abs_move(x=None, y=None, **kwargs):
    write('G90')
    move(x=x, y=y, **kwargs)
    write('G91')


def rect(x, y, direction='CW'):
    """ Trace a rectangle with the given width and height.

    Parameters
    ----------
    x : float
        The width of the rectange in the x dimension.
    y : float
        The heigh of the rectangle in the y dimension.
    direction : either 'CW' or 'CCW'
        Whether to draw the rectangle clockwise or counter clockwise.

    """
    if direction == 'CW':
        move(y=y)
        move(x=x)
        move(y=-y)
        move(x=-x)
    else:
        move(x=x)
        move(y=y)
        move(x=-x)
        move(y=-y)


def meander(x, y, spacing, orientation='x'):
    """ Infill a rectangle with a square wave meandering pattern. If the
    relevant dimension is not a multiple of the spacing, the spacing will be
    tweaked to ensure the dimensions work out.

    Parameters
    ----------
    x : float
        The width of the rectangle in the x dimension.
    y : float
        The heigh of the rectangle in the y dimension.
    spacing : float
        The space between parallel meander lines.
    orientation : str ('x' or 'y')

    """
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
    if actual_spacing != spacing:
        msg = ';WARNING! meander spacing updated from {} to {}'
        write(msg.format(spacing, actual_spacing))
    spacing = actual_spacing
    sign = 1
    for _ in range(int(passes)):
        move(**{major_name: (sign * major)})
        move(**{minor_name: spacing})
        sign = -1 * sign


###############################################################################
### AeroTech Specific Functions
###############################################################################

def toggle_pressure(com_port):
    write('Call togglePress P{}'.format(com_port))


def set_pressure(com_port, value):
    write('Call setPress P{} Q{}'.format(com_port, value))


def set_valve(num, value):
    write('$DO{}.0={}'.format(num, value))


###############################################################################
### Private Interface
###############################################################################

def write(statement):
    print statement


def _format_args(x, y, kwargs):
    args = []
    if x is not None:
        args.append('X{}'.format(x))
    if y is not None:
        args.append('Y{}'.format(y))
    args += ['{}{}'.format(k, v) for k, v in kwargs.items()]
    args = ' '.join(args)
    return args


if __name__ == '__main__':
    setup()
    home()
    move(10, 10)
    meander(10, -5, .2004, 'y')

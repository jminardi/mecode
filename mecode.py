"""
mecode is a collection of functions desiged to simplify generation of GCode.

Relative movements are assumed, unless stated in the function name. Any
function that uses absolute mode always resets back to relative.

"""

import math


###############################################################################
### GCode Aliases
###############################################################################

def set_home(X=0, Y=0, **kwargs):
    args = _format_args(X, Y, kwargs)
    write('G92 ' + args)


def reset_home():
    write('G92.1')


def move(X=None, Y=None, **kwargs):
    args = _format_args(X, Y, kwargs)
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


def abs_move(X=None, Y=None, **kwargs):
    write('G90')
    move(X=X, Y=Y, **kwargs)
    write('G91')


def rect(X, Y, direction='CW'):
    """ Trace a rectangle with the given width and height.

    Parameters
    ----------
    X : float
        The width of the rectange in the X dimension.
    Y : float
        The heigh of the rectangle in the Y dimension.
    direction : either 'CW' or 'CCW'
        Whether to draw the rectangle clockwise or counter clockwise.

    """
    if direction == 'CW':
        move(Y=Y)
        move(X=X)
        move(Y=-Y)
        move(X=-X)
    else:
        move(X=X)
        move(Y=Y)
        move(X=-X)
        move(Y=-Y)


def meander(X, Y, spacing, orientation='X'):
    """ Infill a rectangle with a square wave meandering pattern. If the
    relevant dimension is not a multiple of the spacing, the spacing will be
    tweaked to ensure the dimensions work out.

    Parameters
    ----------
    X : float
        The width of the rectangle in the X dimension.
    Y : float
        The heigh of the rectangle in the Y dimension.
    spacing : float
        The space between parallel meander lines.
    orientation : str ('X' or 'Y')

    """
    # Major axis is the parallel lines, minor axis is the jog.
    if orientation == 'X':
        major, major_name = X, 'X'
        minor, minor_name = Y, 'Y'
    else:
        major, major_name = Y, 'Y'
        minor, minor_name = X, 'X'

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


###############################################################################
### Private Interface
###############################################################################

def write(statement):
    print statement


def _format_args(X, Y, kwargs):
    args = []
    if X is not None:
        args.append('X{}'.format(X))
    if Y is not None:
        args.append('Y{}'.format(Y))
    args += ['{}{}'.format(k, v) for k, v in kwargs.items()]
    args = ' '.join(args)
    return args


if __name__ == '__main__':
    setup()
    home()
    move(10, 10)
    meander(10, -5, .2004, 'Y')

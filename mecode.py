"""
mecode is a collection of functions desiged to simplify generation of GCode.

Relative movements are assumed, unless stated in the function name. Any
function that uses absolute mode always resets back to relative.

"""

import math


###############################################################################
### GCode Aliases
###############################################################################

def home():
    write('G1 X0 Y0')


def set_home(X=0, Y=0, **kwargs):
    args = _format_args(X, Y, kwargs)
    write('G92 ' + args)


def line(X=None, Y=None, **kwargs):
    args = _format_args(X, Y, kwargs)
    write('G1 ' + args)


def feed(rate):
    write('F{}'.format(rate))


###############################################################################
### Composed Functions
###############################################################################

def setup():
    """ Set the environment into a consistent state to start off.
    """
    write('G91')


def abs_line(X=None, Y=None, **kwargs):
    write('G90')
    line(X=X, Y=Y, **kwargs)
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
        line(Y=Y)
        line(X=X)
        line(Y=-Y)
        line(X=-X)
    else:
        line(X=X)
        line(Y=Y)
        line(X=-X)
        line(Y=-Y)


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
        line(**{major_name: (sign * major)})
        line(**{minor_name: spacing})
        sign = -1 * sign


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
    line(10, 10)
    meander(10, -5, .2004, 'Y')

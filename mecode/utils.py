import numpy as np


def profile_surface(g, kp, x_start, x_stop, x_step, y_start, y_stop, y_step):
    """
    Parameters
    ----------
    start : tuple of len 2
        The upper left corner of the rectangle to profile

    Notes
    -----
    Any previously set software homes with be cleared.

    """

    g.clear_home()
    g.abs_move(x_start, y_start)
    x_range = np.arange(x_start, x_stop, x_step)
    y_range = np.arange(y_start, y_stop, y_step)
    surface = np.zeros((len(x_range), len(y_range)))
    for x in x_range:
        for y in y_range:
            g.abs_move(x, y)
            surface[x, y] = kp.read()


def write_cal_file(path, surface, x_start, x_stop, x_step, y_start, y_stop, y_step):
    print path
    with open(path, 'w') as f:
        x_range = np.arange(x_start, x_stop, x_step)
        y_range = np.arange(y_start, y_stop, y_step)
        f.write('Start Stuff')
        for x in x_range:
            for y in y_range:
                f.write('0 0 ' + str(surface[x, y]))
            f.write('\n')
        f.write(':END')

write_cal_file('/Users/jack/Desktop/out.cal', np.ones((2, 3)), 1,1,1,1,1,1)

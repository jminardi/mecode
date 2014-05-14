import numpy as np


def profile_surface(g, kp, x_start, x_stop, x_step, y_start, y_stop, y_step, feed_rate = 5, dwell = 0.1):
    """
    Parameters
    ----------
    start : tuple of len 2
        The upper left corner of the rectangle to profile

    Notes
    -----
    Any previously set software homes with be cleared.

    """
    g.abs_move(x_start, y_start)
    x_range = np.arange(x_start, x_stop, x_step)
    y_range = np.arange(y_start, y_stop, y_step)
    surface = np.zeros((len(x_range), len(y_range)))
    g.feed(feed_rate)
    for i, x in enumerate(x_range):
        for j, y in enumerate(y_range):
            g.abs_move(x, y)
            g.dwell(dwell)
            surface[i, j] = kp.read()
    return surface


def write_cal_file(path, surface, x_start, x_stop, x_step, y_start, y_stop,
                   y_step, x_offset, y_offset, mode='w+', ref_zero=True):
    print path
    if ref_zero is True:
        surface -= surface[0, 0]
    with open(path, mode) as f:
        x_range = np.arange(x_start, x_stop, x_step)
        y_range = np.arange(y_start, y_stop, y_step)
        num_cols = surface.shape[1]
        
        f.write(';        RowAxis  ColumnAxis  OutputAxis1  OutputAxis2  SampDistRow  SampDistCol  NumCols\n')  #noqa
        f.write(':START2D    2          1           1            2           {}          -{}        {}\n'.format(y_step, x_step, num_cols))  #noqa
        f.write(':START2D OUTAXIS3=4 POSUNIT=PRIMARY CORUNIT=PRIMARY OFFSETROW = {} OFFSETCOL={}\n'.format(-(y_start+y_offset), -(x_start+x_offset)))  #noqa
        
        for i, x in enumerate(x_range):
            for j, y in enumerate(y_range):
                f.write('0 0 ' + str(-surface[x, y]) + '\t')
            f.write('\n')
            
        f.write(':END\n')


#profile_surface(g, kp, x_start, x_stop, x_step, y_start, y_stop, y_step):
#write_cal_file('/Users/jack/Desktop/out.cal', np.ones((2, 3)), 1,1,1,1,1,1)
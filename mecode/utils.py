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


def write_cal_file(path, surface, x_start, x_step, y_start, y_step,
                   axis=4, mode='w+', ref_zero=True):
    """ Create a calfile to be read by an Aerotech machine.

    To load this calfile in:
        LOADCALFILE "path/to/file", 2D_CAL

    Parameters
    ----------
    path : str
        Path to output the cal file to
    surface : 2D np.array
        2D array representing the calibration surface. 0th axis is X and 1st
        axis is Y
    x_start : float
        X position in mm of the first coordinate in the array
    x_step : float
        Spacing between the X points in mm
    y_start : float
        Y position in mm of the first coordinate in the array
    y_step : float
        Spacing between the Y points in mm
    axis : int (default: 4)
        The axis to apply this calibration to.
    mode : str
        The mode to open the file in. Change to append to put more than one
        table in the same file
    ref_zero : bool (default: True)
        If true, the whole surface is shifted in Z to make the first element 0.

    """
    if ref_zero is True:
        surface = surface.copy()
        surface -= surface[0, 0]
    surface = surface.T * -1
    with open(path, mode) as f:
        num_cols = surface.shape[1]
        
        f.write(';         RowAxis  ColumnAxis  OutputAxis1  OutputAxis2  SampDistRow  SampDistCol  NumCols\n')  #noqa
        f.write(':START2D  2        1           1            2            {}           {}          {}\n'.format(y_step, -x_step, num_cols))  #noqa
        f.write(':START2D OUTAXIS3={} POSUNIT=PRIMARY CORUNIT=PRIMARY OFFSETROW={} OFFSETCOL={}\n'.format(axis, -y_start, x_start))  #noqa
        
        for row in surface:
            for item in row:
                f.write('0 0 ' + str(item) + '\t')
            f.write('\n')
            
        f.write(':END\n')

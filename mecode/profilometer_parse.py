from collections import defaultdict
import numpy as np

#from mpl_toolkits.mplot3d import Axes3D
#import matplotlib.pyplot as plt


def load_from_file(filename='prof_dump.txt', min_=2000, max_=31000):
    with open(filename) as f:
        all_data = defaultdict(list)
        points = []

        for line in f:
            if line.startswith(':'):
                x, y = [float(s) for s in line[1:].split()]
                points.append((x, y))
            else:
                value = float(line.strip())
                if value > min_ and value < max_:
                    value = (value / 32767) * 12
                    all_data[(x, y)].append(value)
    return all_data, points


def clean_values(values, window=0.2, center=None):
    if center is None:
        center = np.mean(values)
    cleaned = []
    delta = center * window
    for val in values:
        if (center - delta) < val < (center + delta):
            cleaned.append(val)
    return cleaned


def load_and_curate(filename, reset_zero=False):
    """ Load and process the data from the calibration filedump.
    
    Parameters
    ----------
    filename : path
        Path to the file containing the calibration dump
    reset_zero : bool
        If True, make the first point be (0, 0)
        
    Returns
    -------
    cal_data : Nx3 array
        The array containing calibration deltas.
    
    """
    all_data, points = load_from_file(filename)

    cleaned = clean_values(all_data[points[0]])
    cleaned_again = clean_values(cleaned, window=0.02)
    reference_mean = np.mean(cleaned_again)

    total_mean = np.array([np.mean(vals) for vals in all_data.values()]).mean()

    for point, values in all_data.iteritems():
        cleaned = clean_values(values, 0.3, total_mean)
        cleaned_again = clean_values(cleaned, 0.05)
        cleaned_again = clean_values(cleaned_again, 0.02)
        all_data[point] = reference_mean - np.mean(cleaned_again)

    values = np.array([all_data[pt] for pt in points])
    points = np.array(points)
    x = points[:, 0]
    y = points[:, 1]
    z = values

    cal_data = np.array([x, y, z]).T
    if reset_zero:
        cal_data[:, :2] -= cal_data[0, :2]
    return cal_data



#fig = plt.figure()
#ax = fig.gca(projection='3d')
#surf = ax.scatter(x, y, z)

#plt.show()

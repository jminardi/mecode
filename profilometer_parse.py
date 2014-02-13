#! usr/bin/env python

from collections import defaultdict
import numpy as np
np.seterr(invalid='raise')

from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import matplotlib.pyplot as plt


f = open('prof_dump.txt')

all_data = defaultdict(list)
points = []

for line in f:
    if line.startswith(':'):
        x, y = [float(s) for s in line[1:].split()]
        points.append((x, y))
    else:
        value = float(line.strip())
        if value > 2000 and value < 31000:
            value = (value / 32767) * 12
            all_data[(x, y)].append(value)
f.close()

def clean_values(values, window, mean=None):
    if mean is None:
        mean = np.mean(values)
    cleaned = []
    delta = mean * window
    for val in values:
        if val > mean - delta and val < mean + delta:
            cleaned.append(val)
    return cleaned

cleaned = clean_values(all_data[points[0]], window=0.2)
cleaned_again = clean_values(cleaned, window=0.02)
z_ref = np.mean(cleaned_again)
#print z_ref

total_mean = np.array([np.mean(vals) for vals in all_data.values()]).mean()
#print total_mean

for point, values in all_data.iteritems():
    cleaned = clean_values(values, 0.3, total_mean)
    cleaned_again = clean_values(cleaned, 0.05)
    cleaned_again = clean_values(cleaned_again, 0.02)
    all_data[point] = z_ref - np.mean(cleaned_again)

#print all_data
#for point, value in all_data.items():
    #print point, value

values = np.array([all_data[pt] for pt in points])
points = np.array(points)
x = points[:, 0]
y = points[:, 1]
z = values



fig = plt.figure()
ax = fig.gca(projection='3d')
surf = ax.scatter(x, y, z)
#ax.set_zlim(-1.01, 1.01)

#ax.zaxis.set_major_locator(LinearLocator(10))
#ax.zaxis.set_major_formatter(FormatStrFormatter('%.02f'))

#fig.colorbar(surf, shrink=0.5, aspect=5)

plt.show()

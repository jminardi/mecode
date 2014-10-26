
import math
import copy
import numpy as np
from mecode.main import G

class GMatrix(G):
    """This class passes points through a 2D transformation matrix before
    fowarding them to the G class.  A 2D transformation matrix was
    choosen over a 3D transformation matrix because GCode's ARC
    command cannot be arbitrary rotated in a 3 dimensions.

    This lets you write code like:

    def box(g, height, width):
        g.move(0, width)
        g.move(height, 0)
        g.move(0, -width)
        g.move(-height, 0)

    def boxes(g, height, width):
        g.push_matrix()
        box(g, height, width)
        g.rotate(math.pi/8)
        box(g, height, width)
        g.pop_matrix()

    To get two boxes at a 45 degree angle from each other.

    The 2D transformation matrices are arranged in a stack,
    similar to OpenGL.

    numpy is required.

    """
    def __init__(self, *args, **kwargs):
        super(GMatrix, self).__init__(*args, **kwargs)
        self._matrix_setup()

    # Matrix manipulation #####################################################        
    def _matrix_setup(self):
        " Create our matrix stack. "
        self.matrix_stack = [np.identity(2)]

    def push_matrix(self):
        " Push a copy of our current transformation matrix. "
        self.matrix_stack.append(copy.deepcopy(self.matrix_stack[-1]))

    def pop_matrix(self):
        " Pop the matrix stack. "
        self.matrix_stack.pop()

    def rotate(self, angle):
        """Rotate the current transformation matrix around the Z
        axis, in radians. """
        rotation_matrix = np.matrix([[math.cos(angle), -math.sin(angle)],
                                     [math.sin(angle), math.cos(angle)]])

        self.matrix_stack[-1] = rotation_matrix * self.matrix_stack[-1]

    def scale(self, scale):
        " Scale the current transformation matrix. "
        scale_matrix = np.identity(2) * scale
        self.matrix_stack[-1] = scale_matrix * self.matrix_stack[-1]

    def _matrix_transform(self, x, y, z):
        "Transform an x,y,z coordinate by our transformation matrix."
        matrix = self.matrix_stack[-1]

        if x is None: x = 0.0
        if y is None: y = 0.0

        transform = matrix * np.matrix([x, y]).T
        
        return (transform.item(0), transform.item(1), z)

    def _matrix_transform_length(self, length):
        (x,y,z) = self._matrix_transform(length, 0, 0)
        return math.sqrt(x**2 + y**2 + z**2)

    def move(self, x=None, y=None, z=None, **kwargs):
        (x,y,z) = self._matrix_transform(x,y,z)
        super(GMatrix, self).move(x,y,z, **kwargs)

    def arc(self, x=None, y=None, z=None, direction='CW', radius='auto',
            helix_dim=None, helix_len=0, **kwargs):
        (x_prime,y_prime,z_prime) = self._matrix_transform(x,y,z)
        if x is None: x_prime = None
        if y is None: y_prime = None
        if z is None: z_prime = None
        if helix_len: helix_len = self._matrix_transform_length(helix_len)
        super(GMatrix, self).arc(x=x_prime,y=y_prime,z=z_prime,direction=direction,radius=radius,
                                 helix_dim=helix_dim, helix_len=helix_len,
                                 **kwargs)
    @property
    def current_position(self):
        x = self._current_position['x']
        y = self._current_position['y']
        z = self._current_position['z']
        if x is None: x = 0.0
        if y is None: y = 0.0

        matrix = self.matrix_stack[-1]
        transform = matrix.T * np.matrix([x, y]).T
        
        return { 'x':transform.item(0),
                 'y':transform.item(1),
                 'z':z }


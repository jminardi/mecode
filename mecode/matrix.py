
import math
import copy
import numpy as np
from mecode import G

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
        self.position_savepoints = []
        
    # Position savepoints #####################################################        
    def save_position(self):
        self.position_savepoints.append((self.current_position["x"],
                                         self.current_position["y"],
                                         self.current_position["z"]))

    def restore_position(self):
        return_position = self.position_savepoints.pop()
        self.abs_move(return_position[0], return_position[1], return_position[2])


    # Matrix manipulation #####################################################        
    def _matrix_setup(self):
        " Create our matrix stack. "
        self.matrix_stack = [np.matrix([[1.0, 0], [0.0, 1.0]])]

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

    def reflect(self, angle):
        """ Reflect about the line starting from the origin at given angle
        from the x axis.

        Example
        -------
        >>> # reflect about the x axis, such that up is down
        >>> g.reflect(0)
        >>> # reflect about the y axis, such that right is left
        >>> g.reflect(math.pi/2)

        """

        # The transformation matrix for a reflection about a line at angle
        # t from the x axis is
        #
        #  [[cos(2t),  sin(2t)],
        #   [sin(2t), -cos(2t)]]
        #
        # In our case, t is the given angle plus the current angle between vector [1,0]
        # and the absolute x axis, i.e. the angle of the current coordinate system.

        # So first, we get that angle
        x_axis = self.matrix_stack[-1] * np.matrix([1, 0]).T
        x_angle = math.atan2(x_axis.item(1), x_axis.item(0))

        # Now we can set 2t in our adjusted coordinate system
        tt = 2 * (x_angle + angle)

        reflection_matrix = np.matrix([[math.cos(tt), math.sin(tt)],
                                       [math.sin(tt), -1 * math.cos(tt)]])

        self.matrix_stack[-1] = reflection_matrix * self.matrix_stack[-1]

    def _matrix_transform(self, x, y, z):
        "Transform an x,y,z coordinate by our transformation matrix."
        matrix = self.matrix_stack[-1]

        if x is None: x = 0
        if y is None: y = 0

        transform = matrix * np.matrix([x, y]).T
        
        return (transform.item(0), transform.item(1), z)

    def _matrix_transform_length(self, length):
        (x,y,z) = self._matrix_transform(length, 0, 0)
        return math.sqrt(x**2 + y**2 + z**2)

    def abs_move(self, x=None, y=None, z=None, **kwargs):
        if x is None: x = self.current_position['x']
        if y is None: y = self.current_position['y']
        if z is None: z = self.current_position['z']
        # abs_move ends up invoking move, which means that
        # we don't need to do a matrix transform here.
        super(GMatrix, self).abs_move(x,y,z, **kwargs)

    def move(self, x=None, y=None, z=None, **kwargs):
        (x,y,z) = self._matrix_transform(x,y,z)
        super(GMatrix, self).move(x,y,z, **kwargs)

    def _arc_direction_transform(self, direction):
        if np.linalg.det(self.matrix_stack[-1]) < 0:
            direction_reverse = { 'CW' : 'CCW',
                                  'CCW' : 'CW' }
            return direction_reverse[direction]
        return direction

    def arc(self, x=None, y=None, z=None, direction='CW', radius='auto',
            helix_dim=None, helix_len=0, **kwargs):
        (x_prime,y_prime,z_prime) = self._matrix_transform(x,y,z)
        if x is None: x_prime = None
        if y is None: y_prime = None
        if z is None: z_prime = None
        if helix_len: helix_len = self._matrix_transform_length(helix_len)
        direction = self._arc_direction_transform(direction)
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
        transform = matrix.getI() * np.matrix([x, y]).T
        
        return { 'x':transform.item(0),
                 'y':transform.item(1),
                 'z':z }


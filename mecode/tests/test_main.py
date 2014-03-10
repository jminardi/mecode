import os
import unittest
from tempfile import TemporaryFile

from mecode import G

HERE = os.path.dirname(os.path.abspath(__file__))


class TestG(unittest.TestCase):

    def setUp(self):
        self.outfile = TemporaryFile()
        self.g = G(outfile=self.outfile, print_lines=False)

    def tearDown(self):
        self.g.teardown()
        del self.outfile
        del self.g

    def test_init(self):
        self.assertEqual(self.g.movement_mode, 'relative')

    def test_set_home(self):
        g = self.g
        g.set_home()
        expected = 'G92'
        self.assert_output(expected)
        g.set_home(x=10, y=20, A=5)
        expected += """
        G92 X10.000000 Y20.000000 A5.000000"""
        self.assert_output(expected)
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 20.0})
        g.set_home(y=0)
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 0.0})

    def test_reset_home(self):
        self.g.reset_home()
        expected = 'G92.1'
        self.assert_output(expected)

    def test_relative(self):
        self.g.relative()
        self.assertEqual(self.g.movement_mode, 'relative')
        self.assert_output('G91')

    def test_absolute(self):
        self.g.absolute()
        self.assertEqual(self.g.movement_mode, 'absolute')
        self.assert_output('G90')

    def test_feed(self):
        self.g.feed(10)
        self.assert_output('F10')

    def test_dwell(self):
        self.g.dwell(10)
        self.assert_output('G4 P10')

    def test_setup(self):
        self.g.setup()
        expected = open(os.path.join(HERE, '../header.txt')).read()
        self.assert_output(expected)

    def test_home(self):
        self.g.home()
        expected = """
        G90
        G1 X0.000000 Y0.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0})

    def test_move(self):
        g = self.g
        g.move(10, 10)
        self.assert_position({'x': 10.0, 'y': 10.0})
        g.move(10, 10, A=50)
        self.assert_position({'x': 20.0, 'y': 20.0, 'A': 50})
        expected = """
        G1 X10.000000 Y10.000000
        G1 X10.000000 Y10.000000 A50.000000
        """
        self.assert_output(expected)

    def test_abs_move(self):
        self.g.abs_move(10, 10)
        expected = """
        G90
        G1 X10.000000 Y10.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 10, 'y': 10})
        self.g.abs_move(5, 5)
        expected += """
        G90
        G1 X5.000000 Y5.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 5, 'y': 5})
        self.g.abs_move(15, 0, D=5)
        expected += """
        G90
        G1 X15.000000 Y0.000000 D5.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 15, 'y': 0, 'D': 5})

    ### helper functions  #####################################################

    def assert_output(self, expected):
        if isinstance(expected, basestring):
            expected = expected.split('\n')
        expected = [x.strip() for x in expected if x.strip()]
        self.outfile.seek(0)
        lines = self.outfile.readlines()
        lines = [x.strip() for x in lines if x.strip()]
        self.assertListEqual(lines, expected)

    def assert_position(self, expected):
        self.assertEqual(self.g.current_position, expected)


if __name__ == '__main__':
    unittest.main()

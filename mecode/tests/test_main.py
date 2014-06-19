import os.path
import unittest
from tempfile import TemporaryFile
import sys
from os.path import abspath, dirname


HERE = dirname(abspath(__file__))

try:
    from mecode import G, is_str, decode2To3
except:
    sys.path.append(abspath(os.path.join(HERE, '..','..')))
    from mecode import G, is_str, decode2To3

class TestG(unittest.TestCase):

    def setUp(self):
        self.outfile= TemporaryFile()
        self.g = G(outfile=self.outfile, print_lines=False,
                   aerotech_include=False)

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
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 20.0, 'z': 0})
        g.set_home(y=0)
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 0.0, 'z': 0})

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
        self.outfile = TemporaryFile()
        self.g = G(outfile=self.outfile, print_lines=False)
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
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

    def test_move(self):
        g = self.g
        g.move(10, 10)
        self.assert_position({'x': 10.0, 'y': 10.0, 'z': 0})
        g.move(10, 10, A=50)
        self.assert_position({'x': 20.0, 'y': 20.0, 'A': 50, 'z': 0})
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
        self.assert_position({'x': 10, 'y': 10, 'z': 0})

        self.g.abs_move(5, 5)
        expected += """
        G90
        G1 X5.000000 Y5.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 5, 'y': 5, 'z': 0})

        self.g.abs_move(15, 0, D=5)
        expected += """
        G90
        G1 X15.000000 Y0.000000 D5.000000
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 15, 'y': 0, 'D': 5, 'z': 0})

    def test_arc(self):
        with self.assertRaises(RuntimeError):
            self.g.arc()

        self.g.arc(x=10, y=0)
        expected = """
        G17
        G2 Y0 X10 R5.0
        """
        self.assert_output(expected)
        self.assert_position({'x': 10, 'y': 0, 'z': 0})

        self.g.arc(x=5, A=0, direction='CCW', radius=5)
        expected += """
        G16 X Y A
        G18
        G3 A0 X5 R5
        """
        self.assert_output(expected)
        self.assert_position({'x': 15, 'y': 0, 'A': 0, 'z': 0})

        self.g.arc(x=0, y=10, helix_dim='D', helix_len=10)
        expected += """
        G16 X Y D
        G17
        G2 Y10 X0 R5.0 G1 D10
        """
        self.assert_output(expected)
        self.assert_position({'x': 15, 'y': 10, 'A': 0, 'D': 10, 'z': 0})

        with self.assertRaises(RuntimeError):
            self.g.arc(x=10, y=10, radius=1)

    def test_abs_arc(self):
        self.g.abs_arc(x=0, y=10)
        expected = """
        G90
        G17
        G2 Y10 X0 R5.0
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 10, 'z': 0})

        self.g.abs_arc(x=0, y=10)
        expected += """
        G90
        G17
        G2 Y10 X0 R0.0
        G91
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 10, 'z': 0})

    def test_rect(self):
        self.g.rect(10, 5)
        expected = """
        G1 Y5.000000
        G1 X10.000000
        G1 Y-5.000000
        G1 X-10.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UL')
        expected += """
        G1 X10.000000
        G1 Y-5.000000
        G1 X-10.000000
        G1 Y5.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UR')
        expected += """
        G1 Y-5.000000
        G1 X-10.000000
        G1 Y5.000000
        G1 X10.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LR')
        expected += """
        G1 X-10.000000
        G1 Y5.000000
        G1 X10.000000
        G1 Y-5.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LL', direction='CCW')
        expected += """
        G1 X10.000000
        G1 Y5.000000
        G1 X-10.000000
        G1 Y-5.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UL', direction='CCW')
        expected += """
        G1 Y-5.000000
        G1 X10.000000
        G1 Y5.000000
        G1 X-10.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UR', direction='CCW')
        expected += """
        G1 X-10.000000
        G1 Y-5.000000
        G1 X10.000000
        G1 Y5.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LR', direction='CCW')
        expected += """
        G1 Y5.000000
        G1 X-10.000000
        G1 Y-5.000000
        G1 X10.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

    def test_meander(self):
        self.g.meander(2, 2, 1)
        expected = """
        G91
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 2, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1.1)
        expected += """
        ;WARNING! meander spacing updated from 1.1 to 1.0
        G91
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 4, 'y': 4, 'z': 0})

        self.g.meander(2, 2, 1, start='UL')
        expected += """
        G91
        G1 X2.000000
        G1 Y-1.000000
        G1 X-2.000000
        G1 Y-1.000000
        G1 X2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 6, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1, start='UR')
        expected += """
        G91
        G1 X-2.000000
        G1 Y-1.000000
        G1 X2.000000
        G1 Y-1.000000
        G1 X-2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 4, 'y': 0, 'z': 0})

        self.g.meander(2, 2, 1, start='LR')
        expected += """
        G91
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 2, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1, start='LR', orientation='y')
        expected += """
        G91
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        G1 X-1.000000
        G1 Y2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 4, 'z': 0})

        self.g.meander(3, 2, 1, start='LR', orientation='y')
        expected += """
        G91
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        G1 X-1.000000
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        """
        self.assert_output(expected)
        self.assert_position({'x': -3, 'y': 4, 'z': 0})

    def test_clip(self):
        self.g.clip()
        expected = """
        G16 X Y Z
        G18
        G3 X0 Z4 R2.0
        """
        self.assert_output(expected)
        self.assert_position({'y': 0, 'x': 0, 'z': 4})

        self.g.clip(axis='A', direction='-y', height=10)
        expected += """
        G16 X Y A
        G19
        G2 Y0 A10 R5.0
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 4, 'A': 10})

        self.g.clip(axis='A', direction='-y', height=-10)
        expected += """
        G16 X Y A
        G19
        G3 Y0 A-10 R5.0
        """
        self.assert_output(expected)
        self.assert_position({'x': 0, 'y': 0, 'z': 4, 'A': 0})

    def test_toggle_pressure(self):
        self.g.toggle_pressure(0)
        expected = 'Call togglePress P0'
        self.assert_output(expected)

    def test_align_nozzle(self):
        self.g.align_nozzle('A')
        expected = 'Call alignNozzle Q-15 R0.1 L1 I-72 J1'
        self.assert_output(expected)
        with self.assertRaises(RuntimeError):
            self.g.align_nozzle('F')

    def test_align_zero_nozzle(self):
        self.g.align_zero_nozzle('A')
        expected = 'Call alignZeroNozzle Q-15 R0.1 L1 I-72 J1'
        self.assert_output(expected)
        with self.assertRaises(RuntimeError):
            self.g.align_zero_nozzle('F')

    def test_set_pressure(self):
        self.g.set_pressure(0, 10)
        expected = 'Call setPress P0 Q10'
        self.assert_output(expected)

    def test_set_valve(self):
        self.g.set_valve(0, 1)
        expected = '$DO0.0=1'
        self.assert_output(expected)

    def test_save_alignment(self):
        self.g.save_alignment()
        expected = 'Call save_value Q1'
        self.assert_output(expected)

    ### helper functions  #####################################################

    def assert_output(self, expected):
        if is_str(expected):
            expected = expected.split('\n')
        expected = [x.strip() for x in expected if x.strip()]
        self.outfile.seek(0)
        lines = self.outfile.readlines()
        lines = [decode2To3(x).strip() for x in lines if x.strip()]
        self.assertListEqual(lines, expected)

    def assert_position(self, expected):
        self.assertEqual(self.g.current_position, expected)


if __name__ == '__main__':
    unittest.main()

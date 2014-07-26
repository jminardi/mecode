import os.path
import unittest
from tempfile import TemporaryFile
import sys
from os.path import abspath, dirname


HERE = dirname(abspath(__file__))

try:
    from mecode import G, is_str, decode2To3
except:
    sys.path.append(abspath(os.path.join(HERE, '..', '..')))
    from mecode import G, is_str, decode2To3


class TestG(unittest.TestCase):

    def setUp(self):
        self.outfile = TemporaryFile()
        self.g = G(outfile=self.outfile, print_lines=False,
                   aerotech_include=False)
        self.expected = ""
        if self.g.is_relative:
            self.expect_cmd('G91')
        else:
            self.expect_cmd('G90')

    def tearDown(self):
        self.g.teardown()
        del self.outfile
        del self.g

    def test_init(self):
        self.assertEqual(self.g.is_relative, True)

    def test_set_home(self):
        g = self.g
        g.set_home()
        self.expect_cmd('G92')
        self.assert_output()
        g.set_home(x=10, y=20, A=5)
        self.expect_cmd('G92 X10.000000 Y20.000000 A5.000000')
        self.assert_output()
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 20.0, 'z': 0})
        g.set_home(y=0)
        self.assert_position({'A': 5.0, 'x': 10.0, 'y': 0.0, 'z': 0})

    def test_reset_home(self):
        self.g.reset_home()
        self.expect_cmd('G92.1')
        self.assert_output()

    def test_relative(self):
        self.assertEqual(self.g.is_relative, True)
        self.g.absolute()
        self.expect_cmd('G90')
        self.g.relative()
        self.assertEqual(self.g.is_relative, True)
        self.expect_cmd('G91')
        self.assert_output()
        self.g.relative()
        self.assertEqual(self.g.is_relative, True)
        self.assert_output()

    def test_absolute(self):
        self.g.absolute()
        self.assertEqual(self.g.is_relative, False)
        self.expect_cmd('G90')
        self.assert_output()
        self.g.absolute()
        self.assertEqual(self.g.is_relative, False)
        self.assert_output()

    def test_feed(self):
        self.g.feed(10)
        self.expect_cmd('F10')
        self.assert_output()

    def test_dwell(self):
        self.g.dwell(10)
        self.expect_cmd('G4 P10')
        self.assert_output()

    def test_setup(self):
        self.outfile = TemporaryFile()
        self.g = G(outfile=self.outfile, print_lines=False)
        self.expected = ""
        self.expect_cmd(open(os.path.join(HERE, '../header.txt')).read())
        self.expect_cmd('G91')
        self.assert_output()

    def test_home(self):
        self.g.home()
        self.expect_cmd("""
        G90
        G1 X0.000000 Y0.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

    def test_move(self):
        g = self.g
        g.move(10, 10)
        self.assert_position({'x': 10.0, 'y': 10.0, 'z': 0})
        g.move(10, 10, A=50)
        self.assert_position({'x': 20.0, 'y': 20.0, 'A': 50, 'z': 0})
        g.move(10, 10, 10)
        self.assert_position({'x': 30.0, 'y': 30.0, 'A': 50, 'z': 10})
        self.expect_cmd("""
        G1 X10.000000 Y10.000000
        G1 X10.000000 Y10.000000 A50.000000
        G1 X10.000000 Y10.000000 Z10.000000
        """)
        self.assert_output()

    def test_abs_move(self):
        self.g.relative()
        self.g.abs_move(10, 10)
        self.expect_cmd("""
        G90
        G1 X10.000000 Y10.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 10, 'y': 10, 'z': 0})

        self.g.abs_move(5, 5, 5)
        self.expect_cmd("""
        G90
        G1 X5.000000 Y5.000000 Z5.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 5, 'y': 5, 'z': 5})

        self.g.abs_move(15, 0, D=5)
        self.expect_cmd("""
        G90
        G1 X15.000000 Y0.000000 D5.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 15, 'y': 0, 'D': 5, 'z': 5})

        self.g.absolute()
        self.g.abs_move(19, 18, D=6)
        self.expect_cmd("""
        G90
        G1 X19.000000 Y18.000000 D6.000000
        """)
        self.assert_output()
        self.assert_position({'x': 19, 'y': 18, 'D': 6, 'z': 5})
        self.g.relative()

    def test_arc(self):
        with self.assertRaises(RuntimeError):
            self.g.arc()

        self.g.arc(x=10, y=0)
        self.expect_cmd("""
        G17
        G2 X10.000000 Y0.000000 R5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 10, 'y': 0, 'z': 0})

        self.g.arc(x=5, A=0, direction='CCW', radius=5)
        self.expect_cmd("""
        G16 X Y A
        G18
        G3 X5.000000 A0.000000 R5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 15, 'y': 0, 'A': 0, 'z': 0})

        self.g.arc(x=0, y=10, helix_dim='D', helix_len=10)
        self.expect_cmd("""
        G16 X Y D
        G17
        G2 X0.000000 Y10.000000 R5.000000 G1 D10
        """)
        self.assert_output()
        self.assert_position({'x': 15, 'y': 10, 'A': 0, 'D': 10, 'z': 0})

        self.g.arc(0, 10, helix_dim='D', helix_len=10)
        self.expect_cmd("""
        G16 X Y D
        G17
        G2 X0.000000 Y10.000000 R5.000000 G1 D10
        """)
        self.assert_output()
        self.assert_position({'x': 15, 'y': 20, 'A': 0, 'D': 20, 'z': 0})

        with self.assertRaises(RuntimeError):
            self.g.arc(x=10, y=10, radius=1)

    def test_abs_arc(self):
        self.g.relative()
        self.g.abs_arc(x=0, y=10)
        self.expect_cmd("""
        G90
        G17
        G2 X0.000000 Y10.000000 R5.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 10, 'z': 0})

        self.g.abs_arc(x=0, y=10)
        self.expect_cmd("""
        G90
        G17
        G2 X0.000000 Y10.000000 R0.000000
        G91
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 10, 'z': 0})

        self.g.absolute()
        self.g.abs_arc(x=0, y=20)
        self.expect_cmd("""
        G90
        G17
        G2 X0.000000 Y20.000000 R5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 20, 'z': 0})
        self.g.relative()

    def test_rect(self):
        self.g.rect(10, 5)
        self.expect_cmd("""
        G1 Y5.000000
        G1 X10.000000
        G1 Y-5.000000
        G1 X-10.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UL')
        self.expect_cmd("""
        G1 X10.000000
        G1 Y-5.000000
        G1 X-10.000000
        G1 Y5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UR')
        self.expect_cmd("""
        G1 Y-5.000000
        G1 X-10.000000
        G1 Y5.000000
        G1 X10.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LR')
        self.expect_cmd("""
        G1 X-10.000000
        G1 Y5.000000
        G1 X10.000000
        G1 Y-5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LL', direction='CCW')
        self.expect_cmd("""
        G1 X10.000000
        G1 Y5.000000
        G1 X-10.000000
        G1 Y-5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UL', direction='CCW')
        self.expect_cmd("""
        G1 Y-5.000000
        G1 X10.000000
        G1 Y5.000000
        G1 X-10.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='UR', direction='CCW')
        self.expect_cmd("""
        G1 X-10.000000
        G1 Y-5.000000
        G1 X10.000000
        G1 Y5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

        self.g.rect(10, 5, start='LR', direction='CCW')
        self.expect_cmd("""
        G1 Y5.000000
        G1 X-10.000000
        G1 Y-5.000000
        G1 X10.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 0})

    def test_meander(self):
        self.g.meander(2, 2, 1)
        self.expect_cmd("""
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 2, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1.1)
        self.expect_cmd("""
        ;WARNING! meander spacing updated from 1.1 to 1.0
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 4, 'y': 4, 'z': 0})

        self.g.meander(2, 2, 1, start='UL')
        self.expect_cmd("""
        G1 X2.000000
        G1 Y-1.000000
        G1 X-2.000000
        G1 Y-1.000000
        G1 X2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 6, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1, start='UR')
        self.expect_cmd("""
        G1 X-2.000000
        G1 Y-1.000000
        G1 X2.000000
        G1 Y-1.000000
        G1 X-2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 4, 'y': 0, 'z': 0})

        self.g.meander(2, 2, 1, start='LR')
        self.expect_cmd("""
        G1 X-2.000000
        G1 Y1.000000
        G1 X2.000000
        G1 Y1.000000
        G1 X-2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 2, 'y': 2, 'z': 0})

        self.g.meander(2, 2, 1, start='LR', orientation='y')
        self.expect_cmd("""
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        G1 X-1.000000
        G1 Y2.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 4, 'z': 0})

        self.g.meander(3, 2, 1, start='LR', orientation='y')
        self.expect_cmd("""
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        G1 X-1.000000
        G1 Y2.000000
        G1 X-1.000000
        G1 Y-2.000000
        """)
        self.assert_output()
        self.assert_position({'x': -3, 'y': 4, 'z': 0})

    def test_clip(self):
        self.g.clip()
        self.expect_cmd("""
        G16 X Y Z
        G18
        G3 X0.000000 Z4.000000 R2.000000
        """)
        self.assert_output()
        self.assert_position({'y': 0, 'x': 0, 'z': 4})

        self.g.clip(axis='A', direction='-y', height=10)
        self.expect_cmd("""
        G16 X Y A
        G19
        G2 Y0.000000 A10.000000 R5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 4, 'A': 10})

        self.g.clip(axis='A', direction='-y', height=-10)
        self.expect_cmd("""
        G16 X Y A
        G19
        G3 Y0.000000 A-10.000000 R5.000000
        """)
        self.assert_output()
        self.assert_position({'x': 0, 'y': 0, 'z': 4, 'A': 0})

    def test_toggle_pressure(self):
        self.g.toggle_pressure(0)
        self.expect_cmd('Call togglePress P0')
        self.assert_output()

    def test_set_pressure(self):
        self.g.set_pressure(0, 10)
        self.expect_cmd('Call setPress P0 Q10')
        self.assert_output()

    def test_set_valve(self):
        self.g.set_valve(0, 1)
        self.expect_cmd('$DO0.0=1')
        self.assert_output()

    def test_rename_axis(self):
        self.g.rename_axis(z='A')
        self.g.move(10, 10, 10)
        self.assert_position({'x': 10.0, 'y': 10.0, 'A': 10, 'z': 10})
        self.expect_cmd("""
        G1 X10.000000 Y10.000000 A10.000000
        """)
        self.assert_output()

        self.g.rename_axis(z='B')
        self.g.move(10, 10, 10)
        self.assert_position({'x': 20.0, 'y': 20.0, 'z': 20, 'A': 10, 'B': 10})
        self.expect_cmd("""
        G1 X10.000000 Y10.000000 B10.000000
        """)
        self.assert_output()

        self.g.rename_axis(x='W')
        self.g.move(10, 10, 10)
        self.assert_position({'x': 30.0, 'y': 30.0, 'z': 30, 'A': 10, 'B': 20,
                              'W': 10})
        self.expect_cmd("""
        G1 W10.000000 Y10.000000 B10.000000
        """)
        self.assert_output()

        self.g.rename_axis(x='X')
        self.g.arc(x=10, z=10)
        self.assert_position({'x': 40.0, 'y': 30.0, 'z': 40, 'A': 10, 'B': 30,
                              'W': 10})
        self.expect_cmd("""
        G16 X Y B
        G18
        G2 X10.000000 B10.000000 R7.071068
        """)
        self.assert_output()

        self.g.abs_arc(x=0, z=0)
        self.assert_position({'x': 0.0, 'y': 30.0, 'z': 0, 'A': 10, 'B': 0,
                              'W': 10})
        self.expect_cmd("""
        G90
        G16 X Y B
        G18
        G2 X0.000000 B0.000000 R28.284271
        G91
        """)
        self.assert_output()

    # helper functions  #######################################################

    def expect_cmd(self, cmd):
        self.expected = self.expected + cmd + '\n'

    def assert_output(self):
        string_rep = ""
        if is_str(self.expected):
            string_rep = self.expected
            self.expected = self.expected.split('\n')
        self.expected = [x.strip() for x in self.expected if x.strip()]
        self.outfile.seek(0)
        lines = self.outfile.readlines()
        lines = [decode2To3(x).strip() for x in lines if x.strip()]
        self.assertListEqual(lines, self.expected)
        self.expected = string_rep

    def assert_position(self, expected_pos):
        self.assertEqual(self.g.current_position, expected_pos)


if __name__ == '__main__':
    unittest.main()

#! /usr/bin/env python

import unittest
from mock import Mock
import os
from time import sleep
from threading import Thread
try:
    from threading import _Event as Event
except ImportError:
    # The _Event class was renamed to Event in python 3.
    from threading import Event

import serial

from mecode.printer import Printer

HERE = os.path.dirname(os.path.abspath(__file__))


class TestPrinter(unittest.TestCase):

    def setUp(self):
        self.p = Printer()
        self.p.s = Mock(spec=serial.Serial(), name='MockSerial')
        self.p.s.readline.return_value = 'ok\n'
        self.p.s.timeout = 1
        self.p.s.writeTimeout = 1

    def tearDown(self):
        self.p.paused = False
        self.p.disconnect()

    def test_disconnect(self):
        #disconnect should work without having called start or connect
        self.p.disconnect()

        self.p.start()
        self.assertTrue(self.p._read_thread.is_alive())
        self.p.disconnect()
        self.assertFalse(self.p._read_thread.is_alive())
        self.assertFalse(self.p._print_thread.is_alive())

    def test_load_file(self):
        self.p.load_file(os.path.join(HERE, 'test.gcode'))
        expected = []
        with open(os.path.join(HERE, 'test.gcode')) as f:
            for line in f:
                line = line.strip()
                if ';' in line:  # clear out the comments
                    line = line.split(';')[0]
                if line:
                    expected.append(line)
        self.assertEqual(self.p._buffer, expected)

    def test_sendline(self):
        self.p.start()
        testline = 'no new line'
        self.p.sendline(testline)
        while len(self.p.sentlines) == 0:
            sleep(0.01)
        self.p.s.write.assert_called_with('N1 no new line*44\n')

        testline = 'with new line\n'
        self.p.sendline(testline)
        while len(self.p.sentlines) == 1:
            sleep(0.01)
        self.p.s.write.assert_called_with('N2 with new line*44\n')

    def test_start(self):
        self.assertIsNone(self.p._read_thread)
        self.assertIsNone(self.p._print_thread)
        self.p.start()
        self.assertTrue(self.p._read_thread.is_alive())

    def test_ok_received(self):
        self.assertIsInstance(self.p._ok_received, Event)
        self.assertTrue(self.p._ok_received.is_set())

    def test_printing(self):
        self.assertFalse(self.p.printing)
        self.p.load_file(os.path.join(HERE, 'test.gcode'))
        self.p.start()
        self.assertTrue(self.p.printing)
        while self.p.printing:
            sleep(0.1)
            #print self.p.sentlines[-1]
        self.assertFalse(self.p.printing)

    def test_start_print_thread(self):
        self.assertIsNone(self.p._print_thread)
        self.assertFalse(self.p.stop_printing)
        self.p._start_print_thread()
        self.assertIsInstance(self.p._print_thread, Thread)
        self.assertFalse(self.p.stop_printing)

    def test_start_read_thread(self):
        self.assertIsNone(self.p._read_thread)
        self.assertFalse(self.p.stop_reading)
        self.p._start_read_thread()
        self.assertIsInstance(self.p._read_thread, Thread)
        self.assertFalse(self.p.stop_reading)
        self.assertTrue(self.p._read_thread.is_alive())

    def test_empty_buffer(self):
        self.p.load_file(os.path.join(HERE, 'test.gcode'))
        self.p.start()
        while self.p.printing:
            sleep(0.01)
        self.assertEqual(self.p.s.write.call_count, len(self.p._buffer))
        self.assertEqual(self.p._current_line_idx, len(self.p._buffer))

    def test_pause(self):
        self.p.load_file(os.path.join(HERE, 'test.gcode'))
        self.p.start()
        self.p.paused = True
        self.assertTrue(self.p._print_thread.is_alive())
        sleep(.1)
        expected = self.p._current_line_idx
        sleep(1)
        self.assertEqual(self.p._current_line_idx, expected)
        self.p.paused = False
        while self.p.printing:
            sleep(0.01)
        self.assertNotEqual(self.p._current_line_idx, expected)

    def test_next_line(self):
        self.p.load_file(os.path.join(HERE, 'test.gcode'))
        line = self.p._next_line()
        expected = 'N1 M900*43\n'
        self.assertEqual(line, expected)

        self.p._current_line_idx = 1
        line = self.p._next_line()
        expected = 'N2 G90*18\n'
        self.assertEqual(line, expected)

    def test_get_response_no_threads_running(self):
        with self.assertRaises(RuntimeError):
            self.p.get_response('test')

    def test_get_response_timeout(self):
        self.p._is_read_thread_running = lambda: True
        resp = self.p.get_response('test', timeout=0.2)
        expected = ''
        # We expect to get a blank response when the timeout is hit.
        self.assertEqual(resp, expected)

    #def test_readline_timeout(self):
    #    def side_effect():
    #        yield 'ok '
    #        yield '58404\n'
    #        while True:
    #            yield 'ok\n'
    #    self.p.s.readline.side_effect = side_effect()
    #    with self.assertRaises(RuntimeError):
    #        self.p._start_read_thread()



if __name__ == '__main__':
    unittest.main()

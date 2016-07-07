#! /usr/bin/env python

import unittest
try:
    from mock import Mock
except ImportError:
    # mock is in the standard library as of python 3.3.
    from unittest.mock import Mock
import socket

from mecode.aerotech_printer import AerotechPrinter

class TestAerotechPrinter(unittest.TestCase):

    def setUp(self):
        self.sock = Mock(spec=socket.socket, name=u'MockSocket')
        self.readfile = Mock(name=u'MockSocketFile')
        self.p = AerotechPrinter(None, None,
                                 sock=self.sock,
                                 readfile=self.readfile)
        self.p.connect()

    def tearDown(self):
        self.p.close()

    def test_sendline(self):
        testline = u'no new line'
        self.p.sendline(testline)
        self.p._socket.sendall.assert_called_with(u'no new line\n')
        self.assertEqual(self.p._lines_sent_without_reading, 1)

        testline = u'with new line\n'
        self.p.sendline(testline)
        self.p._socket.sendall.assert_called_with(u'with new line\n')
        self.assertEqual(self.p._lines_sent_without_reading, 2)

    def test_get_response(self):
        # Return raw bytes from reading the socket.
        attrs = { 'readline.return_value': b'%success\n' }
        self.readfile.configure_mock(**attrs)

        resp = self.p.get_response(u'test')
        self.assertEqual(resp, u'success')

    def test_get_response_after_accumulating_lines(self):
        # Return raw bytes from reading the socket.
        attrs = { 'readline.side_effect': [b'%success 1\n', b'%success 2\n'] }
        self.readfile.configure_mock(**attrs)

        self.p.sendline(u'test 1')
        resp = self.p.get_response(u'test 2')
        self.assertEqual(resp, u'success 2')

if __name__ == '__main__':
    unittest.main()

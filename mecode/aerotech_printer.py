import socket
from . import compat

class AerotechPrinter(object):
    """ AerotechPrinter is responsible for communications with a printer via a
    TCP socket.
    """

    """ End of string character used by Aerotech responses. """
    EOS = u'\n'

    SUCCESS_RESPONSE = u'%'

    def __init__(self, host, port, sock=None, readfile=None):
        self.host = host
        self.port = port
        self._connected = False
        if sock is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self._socket = sock
        self._readfile = readfile if readfile is not None else None
        self._lines_sent_without_reading = 0

    def __enter__(self):
        """ Context manager entry """
        if not self._connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Context manager exit """
        self.close()

    def connect(self, s=None):
        self._socket.connect((self.host, self.port))
        if self._readfile is None:
            self._readfile = self._socket.makefile()
        self._connected = True

    def close(self):
        if self._readfile:
            self._readfile.close()
        if self._socket:
            self._socket.close()
        self._connected = False

    def disconnect(self, wait=False):
        """ Alias for close().  Fulfills the Printer interface. """
        self.close()

    def start(self):
        """ Starts a print.  Fulfills the Printer interface. """
        pass

    def sendline(self, line):
        """ Send the given line to the printer

        Parameters
        ----------
        line : str
            A line of GCode to send to the printer.

        """
        if not line.endswith(self.EOS):
            line += self.EOS
        self._socket.sendall(line)

        self._lines_sent_without_reading += 1

    def get_response(self, line, timeout=0):
        """ Send the given line and return the response from the printer.

        Parameters
        ----------
        line : str
            The line to send to the printer

        Returns
        -------
        r : str
            The response from the printer.

        """
        self.sendline(line)

        response = self._read_to_current_line()
        if not response.startswith(self.SUCCESS_RESPONSE):
            raise RuntimeError(response)

        return response[len(self.SUCCESS_RESPONSE):]

    def _read_to_current_line(self):
        if self._lines_sent_without_reading <= 0:
            raise RuntimeError("attempted to read more lines than sent")

        while self._lines_sent_without_reading > 0:
            # This blocks until the line is read.
            line = self._readfile.readline()
            if not line:
                # End of file reached.
                raise RuntimeError("end of file reached trying to read response; the socket was probably closed prematurely")

            self._lines_sent_without_reading -= 1

        return compat.decode2To3(line).rstrip(self.EOS)

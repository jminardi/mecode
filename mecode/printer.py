import os
import logging
from threading import Thread, Event, Lock
from time import sleep

import serial

HERE = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
#fh = logging.FileHandler(os.path.join(HERE, 'voxelface.log'))
#fh.setFormatter(logging.Formatter('%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'))
#logger.addHandler(fh)


class Printer(object):
    """ The Printer object is responsible for serial communications with a
    printer. The printer is expected to be running Marlin firmware.

    """

    def __init__(self, port='/dev/tty.usbmodem1421', baudrate=250000):

        # USB port and baudrate for communication with the printer.
        self.port = port
        self.baudrate = baudrate

        # The Serial object that the printer is communicating on.
        self.s = None

        # List of the responses from the printer.
        self.responses = []

        # List of lines that were sent to the printer.
        self.sentlines = []

        # True if the print thread is alive and sending lines.
        self.printing = False

        # Set to True to pause the print.
        self.paused = False

        # If set to True, the read_thread will be closed as soon as possible.
        self.stop_reading = False

        # If set to True, the print_thread will be closed as soon as possible.
        self.stop_printing = False

        ### Private Attributes  ################################################

        # List of all lines to be sent to the printer.
        self._buffer = []

        # Index into the _buffer of the next line to send to the printer.
        self._current_line_idx = 0

        # This thread continuously sends lines as they appear in self._buffer.
        self._print_thread = None

        # This thread continuously reads lines as they appear from the printer.
        self._read_thread = None

        # Flag used to synchronize the print_thread and the read_thread. An 'ok'
        # needs to be returned for every line sent. When the print_thread sends
        # a line this flag is cleared, and when an 'ok' is received it is set.
        self._ok_received = Event()
        self._ok_received.set()

        # Lock used to ensure serial send/receive events are atomic with the
        # setting/clearing of the `_ok_received` flag.
        self._communication_lock = Lock()

    ###  Printer Interface  ###################################################

    def connect(self):
        """ Instantiate a Serial object using the stored port and baudrate.
        """
        self.s = serial.Serial(self.port, self.baudrate, timeout=3)
        self._ok_received.set()
        self._current_line_idx = 0
        self._buffer = []
        self.responses = []
        self.sentlines = []
        self._start_read_thread()
        while len(self.responses) == 0:
            sleep(0.01)  # wait until the start message is recieved.
        self.responses = []
        logger.debug('Connected to {}'.format(self.s))

    def disconnect(self):
        """ Disconnect from the printer by stopping threads and closing the port
        """
        if self._print_thread is not None:
            self.stop_printing = True
            self._print_thread.join(3)
        if self._read_thread is not None:
            self.stop_reading = True
            self._read_thread.join(3)
        if self.s is not None:
            self.s.close()
            self.s = None
        self.printing = False
        self._current_line_idx = 0
        self._buffer = []
        self.responses = []
        self.sentlines = []
        logger.debug('Disconnected from printer')

    def load_file(self, filepath):
        """ Load the given file into an internal _buffer. The lines will not be
        send until `self._start_print_thread()` is called.

        Parameters
        ----------
        filepath : str
            The path to a text file containing lines of GCode to be printed.

        """
        lines = []
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if ';' in line:  # clear out the comments
                    line = line.split(';')[0]
                if line:
                    lines.append(line)
        self._buffer.extend(lines)

    def start(self):
        """ Starts the read_thread and the _print_thread.
        """
        self._start_read_thread()
        self._start_print_thread()

    def sendline(self, line):
        """ Send the given line over serial by appending it to the send buffer

        Parameters
        ----------
        line : str
            A line of GCode to send to the printer.

        """
        if line:
            line = str(line).strip()
            if ';' in line:  # clear out the comments
                line = line.split(';')[0]
            if line:
                self._buffer.append(line)

    def get_response(self, line):
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
        buf_len = len(self._buffer) + 1
        self.sendline(line)
        while len(self.responses) != buf_len:
            sleep(0.01)
        return self.responses[-1]

    def current_position(self):
        """ Get the current postion of the printer.

        Returns
        -------
        pos : dict
            Dict with keys of 'X', 'Y', 'Z', and 'E' and values of their
            positions

        """
        # example r: X:0.00 Y:0.00 Z:0.00 E:0.00 Count X: 0.00 Y:0.00 Z:0.00
        r = self.get_response("M114")
        r = r.split(' Count')[0].strip().split()
        r = [x.split(':') for x in r]
        pos = dict([(k, float(v)) for k, v in r])
        return pos

    def reset_linenumber(self):
        line = "N0 M110"
        cksm = self._checksum(line)
        line = "{}*{}".format(line, cksm)
        self.sendline(line)

    ###  Private Methods  ######################################################

    def _start_print_thread(self):
        """ Spawns a new thread that will send all lines in the _buffer over
        serial to the printer. This thread can be stopped by setting
        `stop_printing` to True. If a print_thread already exists and is alive,
        this method does nothing.

        """
        if self._print_thread is not None and self._print_thread.is_alive():
            return
        self.printing = True
        self.stop_printing = False
        self._print_thread = Thread(target=self._print_worker, name='Print')
        self._print_thread.setDaemon(True)
        self._print_thread.start()
        logger.debug('print_thread started')

    def _start_read_thread(self):
        """ Spawns a new thread that will continuously read lines from the
        printer. This thread can be stopped by setting `stop_reading` to True.
        If a print_thread already exists and is alive, this method does
        nothing.

        """
        if self._read_thread is not None and self._read_thread.is_alive():
            return
        self.stop_reading = False
        self._read_thread = Thread(target=self._read_worker, name='Read')
        self._read_thread.setDaemon(True)
        self._read_thread.start()
        logger.debug('read_thread started')

    def _print_worker(self):
        """ This method is spawned in the print thread. It loops over every line
        in the _buffer and sends it over serial to the printer.

        """
        while not self.stop_printing:
            _paused = False
            while self.paused is True:
                if _paused is False:
                    logger.debug('Printer.paused is True, waiting...')
                    _paused = True
                sleep(0.01)
            if _paused is True:
                logger.debug('Printer.paused is now False, resuming.')
            if self._current_line_idx < len(self._buffer):
                _waits = 0
                while not self._ok_received.is_set() and not self.stop_printing:
                    _waits += 1
                    if _waits > 1:
                        logger.debug('waiting on _ok_received {}'.format(_waits))
                        logger.debug(self.sentlines[-1] + ' ||||| '+ self.responses[-1])
                    self._ok_received.wait(2)
                line = self._next_line()
                with self._communication_lock:
                    self.s.write(line)
                    self._ok_received.clear()
                    self._current_line_idx += 1
                # Grab the just sent line without line numbers or checksum
                plain_line = self._buffer[self._current_line_idx - 1].strip()
                self.sentlines.append(plain_line)
            else:  # if there aren't new lines wait 10ms and check again
                sleep(0.01)

        self.printing = False

    def _read_worker(self):
        """ This method is spawned in the read thread. It continuously reads
        from the printer over serial and checks for 'ok's.

        """
        full_resp = ''
        while not self.stop_reading:
            if self.s is not None:
                line = self.s.readline()
                if line.startswith('Resend: '):  # example line: "Resend: 143"
                    self._current_line_idx = int(line.split()[1]) - 1
                    logger.debug('Resend Requested - {}'.format(line.strip()))
                    with self._communication_lock:
                        self._ok_received.set()
                    break
                if line:
                    full_resp += line
                if 'ok' in line:
                    with self._communication_lock:
                        self._ok_received.set()
                    self.responses.append(full_resp)
                    full_resp = ''
            else:  # if no printer is attached, wait 10ms to check again.
                sleep(0.01)

    def _next_line(self):
        """ Prepares the next line to be sent to the printer by prepending the
        line number and appending a checksum and newline character.

        """
        line = self._buffer[self._current_line_idx].strip()
        line = 'N{} {}'.format(self._current_line_idx + 1, line)
        checksum = self._checksum(line)
        return '{}*{}\n'.format(line, checksum)

    def _checksum(self, line):
        """ Calclate the checksum by xor'ing all characters together.
        """
        return reduce(lambda a, b: a ^ b, [ord(char) for char in line])

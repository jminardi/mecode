import os
import logging
from threading import Thread, Event, Lock
from time import sleep, time

from concurrent import futures
from future.utils import raise_from
import serial

try:
    reduce
except NameError:
    # In python 3, reduce is no longer imported by default.
    from functools import reduce

HERE = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
#logger.addHandler(logging.StreamHandler())
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

        # If set to True, the read_thread will be closed as soon as possible.
        self.stop_reading = False

        # If set to True, the print_thread will be closed as soon as possible.
        self.stop_printing = False

        # List of all temperature string responses from the printer.
        self.temp_readings = []

        ### Private Attributes  ################################################

        # List of all lines to be sent to the printer.
        self._buffer = []

        # Dictionary mapping response line number to Future waiting for that
        # response line string.
        self._readline_futures = {}

        # Lock used to ensure the state of the _readline_futures data structure.
        self._readline_futures_lock = Lock()

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

        # Lock used to ensure connecting and disconnecting is atomic.
        self._connection_lock = Lock()

        # Internal state of whether printing is paused, initially not paused.
        self._resume_event = Event()
        self._resume_event.set()

        # If False the Printer instacnce does not own the serial object passed
        # in and it should not be closed when finished with.
        self._owns_serial = True

        # This is set to true when a disconnect was requested. If a sendline is
        # called while this is true an error is raised.
        self._disconnect_pending = False

    @property
    def paused(self):
        """ Set to True to pause the print. """
        return not self._resume_event.is_set()

    @paused.setter
    def paused(self, val):
        if val:
            self._resume_event.clear()
        else:
            self._resume_event.set()

    ###  Printer Interface  ###################################################

    def connect(self, s=None):
        """ Instantiate a Serial object using the stored port and baudrate.

        Parameters
        ----------
        s : serial.Serial
            If a serial object is passed in then it will be used instead of
            creating a new one.

        """
        with self._connection_lock:
            if s is None:
                self.s = serial.Serial(self.port, self.baudrate, timeout=3)
            else:
                self.s = s
                self._owns_serial = False
            self._ok_received.set()
            self._current_line_idx = 0
            self._buffer = []
            self.responses = []
            self.sentlines = []
            self._disconnect_pending = False
            self._start_read_thread()
            if s is None:
                while len(self.responses) == 0:
                    sleep(0.01)  # wait until the start message is recieved.
                self.responses = []
        logger.debug('Connected to {}'.format(self.s))

    def disconnect(self, wait=False):
        """ Disconnect from the printer by stopping threads and closing the port

        Parameters
        ----------
        wait : Bool (default: False)
            If true, this method waits until all lines in the buffer have been
            sent and acknowledged before disconnecting.  Clearing the buffer
            isn't guaranteed.  If the read thread isn't running for some reason,
            this function may return without waiting even when wait is set to
            True.

        """
        with self._connection_lock:
            self._disconnect_pending = True
            if wait:
                buf_len = len(self._buffer)
                while buf_len > len(self.responses) and \
                      self._is_read_thread_running():
                    sleep(0.01)  # wait until all lines in the buffer are sent
            if self._print_thread is not None:
                self.stop_printing = True
                timeout = 5 if self.s is None else self.s.writeTimeout + 1
                self._print_thread.join(timeout)
            if self._read_thread is not None:
                self.stop_reading = True
                timeout = 5 if self.s is None else self.s.timeout + 1
                self._read_thread.join(timeout)
            if self.s is not None and self._owns_serial is True:
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
        if self._disconnect_pending:
            msg = 'Attempted to send line after a disconnect was requested: {}'
            raise RuntimeError(msg.format(line))
        if line:
            line = str(line).strip()
            if ';' in line:  # clear out the comments
                line = line.split(';')[0]
            if line:
                self._buffer.append(line)

    def get_response(self, line, timeout=None):
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

        future = self._readline_future(buf_len)
        # Do this thread-still-alive check *after* grabbing a future since the
        # thread now knows about it and can cancel it if the thread dies.
        if not self._is_read_thread_running():
            raise RuntimeError("can't get response from serial since read thread isn't running")
        try:
            # Block and wait for a response.
            resp = future.result(timeout)
        except futures.TimeoutError:
            # Return blank string on timeout.
            resp = ''
        except futures.CancelledError as e:
            raise_from(RuntimeError("can't get response from serial since read thread isn't running: " + str(e)), e)
        return resp

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
        line = "M110 N0"
        self.sendline(line)

    ###  Private Methods  ######################################################

    def _start_print_thread(self):
        """ Spawns a new thread that will send all lines in the _buffer over
        serial to the printer. This thread can be stopped by setting
        `stop_printing` to True. If a print_thread already exists and is alive,
        this method does nothing.

        """
        if self._is_print_thread_running():
            return
        self.printing = True
        self.stop_printing = False
        self._print_thread = Thread(target=self._print_worker_entrypoint, name='Print')
        self._print_thread.setDaemon(True)
        self._print_thread.start()
        logger.debug('print_thread started')

    def _start_read_thread(self):
        """ Spawns a new thread that will continuously read lines from the
        printer. This thread can be stopped by setting `stop_reading` to True.
        If a print_thread already exists and is alive, this method does
        nothing.

        """
        if self._is_read_thread_running():
            return
        self.stop_reading = False
        self._read_thread = Thread(target=self._read_worker_entrypoint, name='Read')
        self._read_thread.setDaemon(True)
        self._read_thread.start()
        logger.debug('read_thread started')

    def _print_worker_entrypoint(self):
        try:
            self._print_worker()
        except BaseException as e:
            logger.exception("Exception running print worker: " + str(e))

    def _read_worker_entrypoint(self):
        try:
            self._read_worker()
        except BaseException as e:
            logger.exception("Exception running read worker: " + str(e))
            # Reject promises by setting exception.  If other threads are
            # waitiing on the promise, this exception will get raised in that
            # thread.
            with self._readline_futures_lock:
                for linenum, future in self._readline_futures.items():
                    # Don't change the future's result if it's already done.
                    if not future.done():
                        future.set_exception(e)
                    del self._readline_futures[linenum]
        finally:
            # Cancel any promises still left.
            with self._readline_futures_lock:
                for linenum, future in self._readline_futures.items():
                    # Don't change the future's result if it's already done.
                    if not future.done():
                        future.cancel()
                    del self._readline_futures[linenum]

    def _is_print_thread_running(self):
        return self._print_thread is not None and self._print_thread.is_alive()

    def _is_read_thread_running(self):
        return self._read_thread is not None and self._read_thread.is_alive()

    def _print_worker(self):
        """ This method is spawned in the print thread. It loops over every line
        in the _buffer and sends it over serial to the printer.

        """
        while not self.stop_printing:
            if self.paused and not self.stop_printing:
                logger.debug('Printer.paused is True, waiting...')
                self._resume_event.wait()
                logger.debug('Printer.paused is now False, resuming.')
            if self._current_line_idx < len(self._buffer):
                self.printing = True
                while not self._ok_received.is_set() and not self.stop_printing:
                    # Note: This wait causes a 1 second delay before responding
                    # to stop_printing.
                    self._ok_received.wait(1)
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
                if line.startswith('T:'):
                    self.temp_readings.append(line)
                if line:
                    full_resp += line
                    # If there is no newline char in the response that means
                    # serial.readline() hit the timeout before a full line. This
                    # means communication has broken down so both threads need
                    # to be closed down.
                    if '\n' not in line:
                        self.printing = False
                        self.stop_printing = True
                        self.stop_reading = True
                        with self._communication_lock:
                            self._ok_received.set()
                        msg = """readline timed out mid-line.
                            last sentline:  {}
                            response:       {}
                        """
                        raise RuntimeError(msg.format(self.sentlines[-1:],
                                                      full_resp))
                if 'ok' in line:
                    with self._communication_lock:
                        self._ok_received.set()
                    linenum = len(self.responses) + 1
                    self._set_readline_result(linenum, full_resp)
                    full_resp = ''
            else:  # if no printer is attached, wait 10ms to check again.
                sleep(0.01)

    def _set_readline_result(self, linenum, result):
        """ Set the result for a given line number.  This resolves the future
        waiting for the response of this line.
        """
        future = self._readline_future(linenum)
        self.responses.append(result)
        # Ideally the future would be set running sooner, when we start reading
        # the line, but that's more complicated and we don't really care.
        if future.set_running_or_notify_cancel():
            # Resolve the future *after* appending to responses.  Some callers
            # may depend on the responses array after waking up.
            future.set_result(result)
        # Remove the reference to the future to prevent a memory leak.
        with self._readline_futures_lock:
            self._readline_futures.pop(linenum, None)

    def _readline_future(self, linenum):
        """ Return a Future to read the given line number. """
        with self._readline_futures_lock:
            if len(self.responses) >= linenum:
                # We already have the response.  Return a future that's already
                # resolved.
                future = futures.Future()
                future.set_result(self.responses[linenum])
                return future

            if linenum in self._readline_futures:
                # We have a cached future.
                return self._readline_futures[linenum]

            # Create a new future and cache it.
            future = futures.Future()
            self._readline_futures[linenum] = future
            return future

    def _next_line(self):
        """ Prepares the next line to be sent to the printer by prepending the
        line number and appending a checksum and newline character.

        """
        line = self._buffer[self._current_line_idx].strip()
        idx = self._current_line_idx + 1 if not line.startswith('M110') else 0
        line = 'N{} {}'.format(idx, line)
        checksum = self._checksum(line)
        return '{}*{}\n'.format(line, checksum)

    def _checksum(self, line):
        """ Calclate the checksum by xor'ing all characters together.
        """
        if not line:
            raise RuntimeError("cannot compute checksum of an empty string")
        return reduce(lambda a, b: a ^ b, [ord(char) for char in line])

import platform
import serial


class BaseSerialDevice(object):

    def __init__(self, comport=None, baud=115200):
        if comport is None:
            if 'Windows' in platform.system():
                self.comport = 'COM5'
            else:
                self.comport = '/dev/ttyUSB0'
        else:
            self.comport = comport
        self.baud = baud
        self.connect()

    def connect(self):
        self.s = serial.Serial(self.comport, baudrate=self.baud,
                               parity='N', stopbits=1, bytesize=8,
                               timeout=2)

    def disconnect(self):
        self.s.close()

    def send(self, msg):
        self.s.write('{}\r\n'.format(msg))
        data = '0'
        while data[-1] != '\r':
            data += self.s.read(self.s.inWaiting())
        return data[1:-1]

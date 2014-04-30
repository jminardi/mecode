import serial


class BaseSerialDevice(object):

    def __init__(self, comport='COM5'):
        self.comport = comport
        self.connect()

    def connect(self):
        self.s = serial.Serial(self.comport, baudrate=115200,
                               parity='N', stopbits=1, bytesize=8)

    def disconnect(self):
        self.s.close()

    def send(self, msg):
        self.s.write('{}\r\n'.format(msg))
        data = '0'
        while data[-1] != '\r':
            data += self.s.read(self.s.inWaiting())
        return data[1:-1]

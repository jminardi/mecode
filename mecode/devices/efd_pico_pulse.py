##############################################################################
#
# For EFD PICO Touch/Pulse controller and jetter
#
##############################################################################

import serial

# Constants
EOT = '\r'
ACK = '<3'

class EFDPicoPulse(object):

    def __init__(self, comport='/dev/ttyUSB0'):
        self.comport = comport
        self.connect()

    def connect(self):
        self.s = serial.Serial(self.comport,
                               baudrate=115200,
                               parity='N',
                               stopbits=1,
                               bytesize=8,
                               timeout=2,
                               write_timeout=2)

    def disconnect(self):
        self.s.close()

    def send(self, command):
        msg = command + EOT
        self.s.write(msg)
        self.s.read_until(ACK)

    def set_valve_mode(mode):



    def set_dispense_count(self, count):



    def get_valve_status(self):
        self.send('rdr1')

    def cycle_valve(self):
        self.send('1cycl')
        self.send('0cycl')

    def set_heater_mode(self, mode):



    def set_heater_temp(self, temp):
        

    def get_heater_status(self):
        self.send('rhtr')

    def get_valve_info(self):
        self.send('info')

    def get_alarm_hist(self):
        self.send('ralr')

    def reset_alarm(self):
        self.send('arst')
    

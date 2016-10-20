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
        # return response and remove ACK
        return self.s.read_until(ACK)[:-2]

    def set_valve_mode(self, mode):
        return self.send(str(mode) + 'drv1')

    def set_dispense_count(self, count):
        return self.send('{:05}'.format(count) + 'dcn1')

    def get_valve_status(self):
        return self.send('rdr1')

    def cycle_valve(self):
        return self.send('1cycl') + self.send('0cycl')

    def set_heater_mode(self, mode):
        """Set heater mode to off, on, or return status.

        Keyword argument:
        mode -- 0 = off; 1 = on; 2 = status; 3 = remote mode"""
        return self.send(str(mode) + 'chtr')

    def set_heater_temp(self, temp):
        """Set heater target to temp between 0-100C."""
        return  self.send('{:05.1f}'.format(temp) + 'stmp')

    def get_heater_status(self):
        return self.send('rhtr')

    def get_valve_info(self):
        return self.send('info')

    def get_alarm_hist(self):
        return self.send('ralr')

    def reset_alarm(self):
        return self.send('arst')
    

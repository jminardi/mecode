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
        """Send message over serial to PicoTouch controller."""
        msg = command + EOT
        self.s.write(msg)
        # return response and remove ACK
        return self.s.read_until(ACK)[:-2]

    def set_valve_mode(self, mode):
        """Set valve mode to Timed, Purge, Continous, or read current mode.

    Keyword argument:
    mode -- 1 = Timed; 2 = Purge; 3 = Continuous; 5 = read current mode """
        return self.send(str(mode) + 'drv1')

    def set_dispense_count(self, count):
        """Set how many times valve dispenses with each cycle."""
        return self.send('{:05}'.format(count) + 'dcn1')

    def get_valve_status(self):
        """Return valve's current parameters and dispense statistics."""
        return self.send('rdr1')

    def cycle_valve(self):
        """Cycle the valve (eqiuvalent to pressing cycle button)."""
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
        """Return mode, heater setpoint temp, and heater actual temp."""
        return self.send('rhtr')

    def get_valve_info(self):
        """Return controller and valve SN and type, fw version, pcb rev."""
        return self.send('info')

    def get_alarm_hist(self):
        """Return last 40 alarm conditions with time and alarm name."""
        return self.send('ralr')

    def reset_alarm(self):
        """Reset a currently active alarm."""
        return self.send('arst')
    

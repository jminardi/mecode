from mecode.devices.base_serial_device import BaseSerialDevice


class KeyenceMicrometer(BaseSerialDevice):

    def start_z_min(self):
        self.set_program(4)
        return self.send('U1')

    def stop_z_min(self):
        val = self.send('L1,0')[4:]
        return float(val)

    def set_program(self, number):
        return self.send('PW,{}'.format(number))

    def get_xy(self):
        self.set_program(3)

    def read(self, output=1):
        """
        Parameters
        ----------
        output : either 1, 2, or 'both'
            Which of the measurement heads to read.
            
        """
        if output == 'both':
            output = 0
        val = self.send('M{},0'.format(output))[3:]
        if output == 0:
            val1, val2 = val.split(',')
            if '--' not in val1:
                return float(val1), float(val2)
            else:
                return None, None
        if '--' not in val:
            return float(val)
        else:
            return None
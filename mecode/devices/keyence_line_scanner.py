from mecode.devices.base_serial_device import BaseSerialDevice


class KeyenceLineScanner(BaseSerialDevice):

    def read(self):
        data = self.send('MS,0,01')
        #if 'F' not in data:
        #    return float(data)
        return data
from mecode.devices.base_serial_device import BaseSerialDevice


class KeyenceProfilometer(BaseSerialDevice):

    def read(self):
        data = self.send('M1')[3:]
        if 'F' not in data:
            return float(data)

    def comm_mode(self):
        return self.send('Q0')

    def norm_mode(self):
        return self.send('R0')

    def set_sampling_rate(self, rate):
        self.comm_mode()
        msg = 'SW,CA,{}\r\n'.format(rate)
        data = self.send(msg)
        self.norm_mode()
        return data

    def set_num_points(self, num):
        self.comm_mode()
        num = str(num).zfill(5)
        msg = 'SW,CI,1,{},0\r\n'.format(num)
        data = self.send(msg)
        self.norm_mode()
        return data

    def start(self):
        return self.send('AS')

    def stop(self):
        return self.send('AP')

    def init(self):
        return self.send('AQ')

    def collect_data(self):
        return self.send('AO,1')

    def accumulation_status(self):
        return self.send('AN')

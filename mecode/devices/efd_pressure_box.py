import serial

STX = '\x02'  #Packet Start
ETX = '\x03'  #Packet End
ACK = '\x06'  #Acknowledge
NAK = '\x15'  #Not Acknowledge
ENQ = '\x05'  #Enquiry
EOT = '\x04'  #End Of Transmission


class EFDPressureBox(object):
    
    def __init__(self, comport='COM4'):
        self.comport = comport
        self.connect()
        
    def connect(self):
        self.s = serial.Serial(self.comport, baudrate=115200,
                               parity='N', stopbits=1, bytesize=8,
                               timeout=2)
    
    def disconnect(self):
        self.s.close()
        
    def send(self, command):
        checksum = self._calculate_checksum(command)
        msg = ENQ + STX + command + checksum + ETX + EOT
        self.s.write(msg)
        self.s.read(self.s.inWaiting())
        
    def set_pressure(self, pressure):
        command = '08PS  {}'.format(str(int(pressure * 10)).zfill(4))
        self.send(command)
        
    def toggle_pressure(self):
        command = '04DI  '
        self.send(command)
        
    def _calculate_checksum(self, string):
        checksum = 0
        for char in string:
            checksum -= ord(char)
        checksum %= 256
        return hex(checksum)[2:].upper()
# Save this file on your ESP32 as mfrc522.py
from machine import Pin, SPI
from os import uname

class MFRC522:
    OK = 0
    NOTAGERR = 1
    ERR = 2

    REQIDL = 0x26
    REQALL = 0x52
    AUTHENT1A = 0x60
    AUTHENT1B = 0x61

    def __init__(self, spi, gpioCs):
        self.spi = spi
        self.cs = Pin(gpioCs, Pin.OUT)
        self.cs.value(1)
        self.init()

    def _wreg(self, reg, val):
        self.cs.value(0)
        self.spi.write(b'%c%c' % ((reg << 1) & 0x7E, val))
        self.cs.value(1)

    def _rreg(self, reg):
        self.cs.value(0)
        self.spi.write(b'%c' % (((reg << 1) & 0x7E) | 0x80))
        val = self.spi.read(1)
        self.cs.value(1)
        return val[0]

    def _set_bit_mask(self, reg, mask):
        self._wreg(reg, self._rreg(reg) | mask)

    def _clear_bit_mask(self, reg, mask):
        self._wreg(reg, self._rreg(reg) & (~mask))

    def init(self):
        self._wreg(0x01, 0x0F) # Reset
        self._wreg(0x2A, 0x8D) # TMode
        self._wreg(0x2B, 0x3E) # TPrescaler
        self._wreg(0x2D, 30)   # TReloadValL
        self._wreg(0x2C, 0)    # TReloadValH
        self._wreg(0x15, 0x40) # TxASK
        self._wreg(0x11, 0x3D) # Mode
        self.antenna_on()

    def antenna_on(self, on=True):
        if on and ~(self._rreg(0x14) & 0x03):
            self._set_bit_mask(0x14, 0x03)
        else:
            self._clear_bit_mask(0x14, 0x03)

    def _tcom(self, cmd, send):
        back = []
        bmask = 0
        irq = 0x00
        irq_en = 0x00
        wait = 0x00

        if cmd == 0x0E: # Authent
            irq_en = 0x12
            wait = 0x10
        elif cmd == 0x0C: # Transceive
            irq_en = 0x77
            wait = 0x30

        self._wreg(0x02, irq_en | 0x80)
        self._clear_bit_mask(0x04, 0x80)
        self._set_bit_mask(0x0A, 0x80)
        self._wreg(0x01, 0x00) # Idle

        for i in send:
            self._wreg(0x09, i)
        
        self._wreg(0x01, cmd)
        
        if cmd == 0x0C:
            self._set_bit_mask(0x0D, 0x80) # StartSend

        i = 2000
        while True:
            n = self._rreg(0x04)
            i -= 1
            if ~((i != 0) and ~(n & 0x01) and ~(n & wait)):
                break

        self._clear_bit_mask(0x0D, 0x80)

        if i == 0:
            return self.ERR, back, bmask

        if ~(self._rreg(0x06) & 0x1B):
            stat = self.OK
            if n & irq_en & 0x01:
                stat = self.NOTAGERR
            elif cmd == 0x0C:
                n = self._rreg(0x0A)
                lbits = self._rreg(0x0C) & 0x07
                if lbits != 0:
                    bmask = (n - 1) * 8 + lbits
                else:
                    bmask = n * 8
                if n == 0:
                    n = 1
                if n > 16:
                    n = 16
                for _ in range(n):
                    back.append(self._rreg(0x09))
        else:
            stat = self.ERR
        return stat, back, bmask

    def request(self, mode):
        self._wreg(0x0D, 0x07)
        stat, back, bits = self._tcom(0x0C, [mode])
        if (stat != self.OK) or (bits != 0x10):
            stat = self.ERR
        return stat, bits

    def anticoll(self):
        self._wreg(0x0D, 0x00)
        stat, back, bits = self._tcom(0x0C, [0x93, 0x20])
        if stat == self.OK:
            if len(back) == 5:
                chk = 0
                for i in range(4):
                    chk = chk ^ back[i]
                if chk != back[4]:
                    stat = self.ERR
            else:
                stat = self.ERR
        return stat, back

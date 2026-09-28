import framebuf

class SH1107(framebuf.FrameBuffer):
    def __init__(self, width, height, i2c, address=0x3c):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(self.height * self.width // 8)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        
        # SH1107 Initialization sequence
        for cmd in [0xAE, 0x00, 0x10, 0xB0, 0xDC, 0x00, 0x81, 0x2F, 0x20, 0xA0, 0xC0, 0xA8, 0x7F, 0xD3, 0x00, 0xD5, 0x50, 0xD9, 0x22, 0xDB, 0x35, 0xAF]:
            self.i2c.writeto(self.address, bytearray([0x80, cmd]))
        self.fill(0)
        self.show()

    def show(self):
        for page in range(self.height // 8):
            self.i2c.writeto(self.address, bytearray([0x80, 0xB0 + page, 0x80, 0x00, 0x80, 0x10]))
            self.i2c.writeto(self.address, b'\x40' + self.buffer[page * self.width:(page + 1) * self.width])

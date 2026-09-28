from machine import Pin, I2C, SPI
import time
import sh1107
from mfrc522 import MFRC522

# ==========================================
# 1. HARDWARE INITIALIZATION
# ==========================================

# Initialize the Grove SH1107 OLED (128x128)
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
oled = sh1107.SH1107(128, 128, i2c)

# Initialize SPI for the RFID Reader
spi = SPI(2, baudrate=1000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(23), miso=Pin(19))
spi.init()

# Initialize RFID Reader (Passing GPIO 5 as the CS pin integer)
try:
    rdr = MFRC522(spi, 5) 
except NameError:
    print("Warning: mfrc522 library not found. RFID disabled.")

# Initialize Directional PIR Sensors
pir_outer = Pin(32, Pin.IN)
pir_inner = Pin(33, Pin.IN)

# Initialize Screen Toggle Button
btn_toggle = Pin(13, Pin.IN, Pin.PULL_UP) 

# Initialize Ultrasonic Height Sensor
trig = Pin(26, Pin.OUT)
echo = Pin(27, Pin.IN)

# Initialize Buzzer
buzzer = Pin(25, Pin.OUT)
buzzer.value(0) 


# ==========================================
# 2. DATABASE & STATE VARIABLES
# ==========================================

# Map Student UIDs to Names
student_db = {
    "0x400805cc": "Praneet Ghosh",  
    "0x98765432": "Student B"
}

# Map Master Override UID (Teacher)
master_card_uid = "0x1234abcd"      

# System States
headcount = 0
is_unlocked = False
unlock_timer = 0
teacher_override = False
override_timer = 0

status_msg = "System Ready"
last_scanned_name = "None"
current_screen = 0 

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def get_distance():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    timeout = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), timeout) > 30000: return 200
    t1 = time.ticks_us()
    
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), t1) > 30000: return 200
    t2 = time.ticks_us()
    
    return (time.ticks_diff(t2, t1) * 0.034) / 2

def update_display():
    oled.fill(0)
    if current_screen == 0:
        oled.text("--- LIVE COUNT ---", 0, 0)
        oled.text(f"Total: {headcount}", 10, 30)
        oled.text(status_msg, 0, 60)
    elif current_screen == 1:
        oled.text("--- LAST SCAN ---", 0, 0)
        oled.text("Name:", 0, 20)
        oled.text(last_scanned_name, 0, 35)
        oled.text(status_msg, 0, 60)
    oled.show()

update_display()


# ==========================================
# 4. MAIN NON-BLOCKING LOOP
# ==========================================

while True:
    current_time = time.ticks_ms()
    display_needs_update = False

    # --- A. Screen Toggle Logic ---
    if btn_toggle.value() == 0:
        current_screen = 1 if current_screen == 0 else 0
        display_needs_update = True
        time.sleep(0.3) 

    # --- B. RFID Scanning Logic ---
    try:
        (stat, tag_type) = rdr.request(rdr.REQIDL)
        if stat == rdr.OK:
            (stat, uid) = rdr.anticoll()
            if stat == rdr.OK:
                
                # Buzzer Beep
                buzzer.value(1)
                time.sleep(0.1) 
                buzzer.value(0)
                
                # Format UID and print
                uid_string = "0x%02x%02x%02x%02x" % (uid[0], uid[1], uid[2], uid[3])
                print("Scanned UID:", uid_string)
                
                # Check database
                if uid_string == master_card_uid:
                    teacher_override = True
                    override_timer = current_time
                    status_msg = "Master Unlocked"
                    last_scanned_name = "Instructor"
                elif uid_string in student_db:
                    is_unlocked = True
                    unlock_timer = current_time
                    status_msg = "Student Unlocked"
                    last_scanned_name = student_db[uid_string]
                else:
                    status_msg = "Unknown Card!"
                    last_scanned_name = "Unregistered"
                
                display_needs_update = True
                time.sleep(1) 
    except NameError:
        pass 

    # --- C. Handle Timers ---
    if is_unlocked and time.ticks_diff(current_time, unlock_timer) > 3000:
        is_unlocked = False
        status_msg = "Scan Expired!"
        display_needs_update = True
        
    if teacher_override and time.ticks_diff(current_time, override_timer) > 5000:
        teacher_override = False
        status_msg = "System Ready"
        display_needs_update = True

    # --- D. Anti-Proxy Entry Logic ---
    if pir_outer.value() == 1:
        wait_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), wait_start) < 1500:
            if pir_inner.value() == 1:
                distance = get_distance()
                if distance < 100: 
                    headcount += 1
                    if is_unlocked or teacher_override:
                        status_msg = "Entry Validated"
                        is_unlocked = False 
                    else:
                        status_msg = "PROXY ATTEMPT!"
                else:
                    status_msg = "Hand Swipe Ignored"
                
                display_needs_update = True
                time.sleep(1)
                break

    # --- E. Exit Logic ---
    elif pir_inner.value() == 1:
        wait_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), wait_start) < 1500:
            if pir_outer.value() == 1:
                if headcount > 0:
                    headcount -= 1
                status_msg = "Valid Exit"
                display_needs_update = True
                time.sleep(1)
                break

    # --- F. Refresh Screen ---
    if display_needs_update:
        update_display()

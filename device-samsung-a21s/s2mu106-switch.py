#!/usr/bin/python3
import os, sys, time, fcntl, json

I2C_SLAVE_FORCE = 0x0706
BUS = "/dev/i2c-0"
JSON_PATH = "/etc/s2mu106_working_state.json"

def log(msg):
    print(msg)
    try:
        with open("/dev/kmsg", "w") as k:
            k.write("<6>[s2mu106-switch] " + str(msg) + "\n")
    except Exception:
        pass

log("Starting comprehensive S2MU106 switch and charger initialization...")

for attempt in range(20):
    if os.path.exists(BUS):
        break
    time.sleep(0.5)

if not os.path.exists(BUS):
    log("ERROR: " + BUS + " not found")
    sys.exit(1)

try:
    fd = os.open(BUS, os.O_RDWR)
except Exception as e:
    log("ERROR: cannot open " + BUS + ": " + str(e))
    sys.exit(1)

def write_reg(addr, reg, val):
    fcntl.ioctl(fd, I2C_SLAVE_FORCE, addr)
    os.write(fd, bytes([reg, val]))

def read_reg(addr, reg):
    fcntl.ioctl(fd, I2C_SLAVE_FORCE, addr)
    os.write(fd, bytes([reg]))
    return os.read(fd, 1)[0]

# 1. Restore from JSON if present
restore_map = {
    0x3C: list(range(0x03, 0x09)) + list(range(0x0A, 0x0D)) + list(range(0x10, 0x15)) + list(range(0x18, 0x24)) + [0x26, 0x27, 0x2E, 0x2F, 0x31, 0x35, 0x36, 0x3E, 0x3F] + list(range(0x40, 0x45)) + [0x90, 0xB3, 0xB4, 0xB7, 0xF6, 0xF8, 0xF9],
    0x3D: list(range(0x18, 0x26)) + list(range(0x60, 0x72)),
    0x3E: list(range(0x09, 0x26)) + [0x59] + list(range(0x66, 0x72))
}

if os.path.exists(JSON_PATH):
    try:
        with open(JSON_PATH) as f:
            dumps = json.load(f)
        for addr, reg_list in restore_map.items():
            saved = dumps.get(hex(addr), [])
            for reg in reg_list:
                if reg < len(saved) and saved[reg] is not None:
                    try:
                        write_reg(addr, reg, saved[reg])
                    except Exception:
                        pass
        log("Restored full S2MU106 state from JSON")
    except Exception as e:
        log("Warning: could not restore full JSON: " + str(e))

# 2. Explicitly enforce critical switch & charger registers
# 0x3C: Type-C CC Rd termination & Sink mode
try:
    write_reg(0x3C, 0x03, 0x78)
    write_reg(0x3C, 0x04, 0x90)
    write_reg(0x3C, 0x05, 0x77)
    write_reg(0x3C, 0x06, 0x88)
    write_reg(0x3C, 0x07, 0x46)
except Exception as e:
    log("Warning 0x3C enforce: " + str(e))

# 0x3D: AP USB switch + Fast charging (2.0A input limit, 1.4A charge current) + Watchdog disabled
try:
    write_reg(0x3D, 0x19, 0x73) # 2.0A input current limit
    write_reg(0x3D, 0x1B, 0x38) # 1.4A fast charge current
    write_reg(0x3D, 0x24, 0x01) # Kick charger watchdog
    write_reg(0x3D, 0x24, 0x00) # Disable charger watchdog timer (prevents WD_SUSPEND)
    write_reg(0x3D, 0x18, 0x01) # Charger toggle off
    time.sleep(0.1)
    write_reg(0x3D, 0x18, 0x03) # Charging mode enabled
    write_reg(0x3D, 0x6D, 0x98) # CTRL1 manual
    write_reg(0x3D, 0x70, 0x77) # MANUAL_SW_CTRL: AP USB
    v_3d_6d = read_reg(0x3D, 0x6D)
    v_3d_70 = read_reg(0x3D, 0x70)
except Exception as e:
    log("Warning 0x3D enforce: " + str(e))
    v_3d_6d = 0
    v_3d_70 = 0

# 0x3E: Secondary switch + MUIC VBUS attach detection
try:
    write_reg(0x3E, 0x09, 0xFC)
    write_reg(0x3E, 0x0A, 0x7A)
    write_reg(0x3E, 0x0B, 0xFF)
    write_reg(0x3E, 0x0C, 0xFF)
    write_reg(0x3E, 0x6D, 0x12)
    write_reg(0x3E, 0x70, 0x24)
    v_3e_70 = read_reg(0x3E, 0x70)
except Exception as e:
    v_3e_70 = 0

os.close(fd)
log(f"SUCCESS: S2MU106 ready! 0x3D: 6D=0x{v_3d_6d:02x}, 70=0x{v_3d_70:02x} | 0x3E: 70=0x{v_3e_70:02x}")

#!/usr/bin/env python3
"""
Samsung Galaxy A21s Display & Backlight Controller
Controls Texas Instruments LM36274 backlight & bias IC via Exynos 850 hardware I2C-1,
plus GPIO HWEN power line (gpg2-1) and Linux framebuffer blanking.

Hardware mapping:
  - HWEN: gpg2-1 (pinctrl_peri 0x139b00a4, bit 1, mask 0x02, Active HIGH)
  - RST:  gpg2-4 (pinctrl_peri 0x139b00a4, bit 4, mask 0x10, Active HIGH - KEEP HIGH!)
  - I2C1: Exynos I2C-1 controller at 0x13840000 on pins gpp0-2 (SCL) and gpp0-3 (SDA)
  - LM36274: Slave Address 0x11
      Reg 0x08: Backlight Enable (0x1F = BL_EN + 4 strings enabled)
      Reg 0x04 / 0x05: Brightness LSB / MSB (11-bit)
      Reg 0x09: Bias Config (0x1E = VPOS & VNEG LCD bias enable, I2C mode)

Usage:
  a21s-display off             Turn off backlight (power saving)
  a21s-display on              Turn on backlight (100% full brightness)
  a21s-display brightness <1-100>  Set backlight brightness percentage
  a21s-display status          Show current display and backlight power state
  a21s-display toggle          Toggle between on and off
"""

import sys
import os
import mmap
import struct
import time
import subprocess

PINCTRL_PERI_BASE = 0x139B0000
I2C1_BASE = 0x13840000
PAGESIZE = 4096

# Offsets in pinctrl_peri
GPP0_CON_OFF = 0x020
GPG2_DAT_OFF = 0x0A4

# Pin masks on gpg2
BL_EN_MASK = 0x02   # Pin 1: HWEN (1 = Powered, 0 = Shutdown)
RST_MASK = 0x10     # Pin 4: gpio_lcd_rst (1 = Normal, MUST REMAIN 1)

LM36274_I2C_ADDR = 0x11
IICCON_VAL = 0xAF   # ACKEN | Tx/Rx Int | Prescaler

def check_root():
    if os.geteuid() != 0:
        print("Error: Root privileges required to access display hardware.", file=sys.stderr)
        print("Please run with sudo: sudo a21s-display [on|off|status|toggle]", file=sys.stderr)
        sys.exit(1)

def hw_i2c_write(mem_i2c, addr, data_bytes):
    struct.pack_into("<I", mem_i2c, 0x00, IICCON_VAL)
    struct.pack_into("<I", mem_i2c, 0x0c, (addr << 1) & 0xfe)
    struct.pack_into("<I", mem_i2c, 0x04, 0xf0) # Master TX, Start
    for _ in range(1000):
        if struct.unpack_from("<I", mem_i2c, 0x00)[0] & 0x10:
            break
        time.sleep(0.0001)
    else:
        struct.pack_into("<I", mem_i2c, 0x04, 0xd0)
        return False
    if struct.unpack_from("<I", mem_i2c, 0x04)[0] & 0x01: # NACK
        struct.pack_into("<I", mem_i2c, 0x04, 0xd0)
        struct.pack_into("<I", mem_i2c, 0x00, IICCON_VAL & ~0x10)
        return False
    for b in data_bytes:
        struct.pack_into("<I", mem_i2c, 0x0c, b)
        struct.pack_into("<I", mem_i2c, 0x00, IICCON_VAL & ~0x10)
        for _ in range(1000):
            if struct.unpack_from("<I", mem_i2c, 0x00)[0] & 0x10:
                break
            time.sleep(0.0001)
        else:
            struct.pack_into("<I", mem_i2c, 0x04, 0xd0)
            return False
        if struct.unpack_from("<I", mem_i2c, 0x04)[0] & 0x01:
            struct.pack_into("<I", mem_i2c, 0x04, 0xd0)
            struct.pack_into("<I", mem_i2c, 0x00, IICCON_VAL & ~0x10)
            return False
    struct.pack_into("<I", mem_i2c, 0x04, 0xd0) # Stop
    struct.pack_into("<I", mem_i2c, 0x00, IICCON_VAL & ~0x10)
    time.sleep(0.001)
    return True

STATE_FILE = "/run/a21s-backlight.state"

def get_hardware_state():
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        mem = mmap.mmap(fd, PAGESIZE, mmap.MAP_SHARED, mmap.PROT_READ, offset=PINCTRL_PERI_BASE)
        try:
            gpg2 = struct.unpack_from("<I", mem, GPG2_DAT_OFF)[0]
            is_panel_rst = bool(gpg2 & RST_MASK)
            is_bl_on = True
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r") as f:
                        if f.read().strip() == "off":
                            is_bl_on = False
                except Exception:
                    pass
            return is_bl_on, is_panel_rst, gpg2
        finally:
            mem.close()
    finally:
        os.close(fd)

def configure_i2c_pins(mem_peri):
    con = struct.unpack_from("<I", mem_peri, GPP0_CON_OFF)[0]
    con = (con & ~0xff00) | 0x2200
    struct.pack_into("<I", mem_peri, GPP0_CON_OFF, con)

def turn_off():
    check_root()
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        mem_peri = mmap.mmap(fd, PAGESIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PINCTRL_PERI_BASE)
        mem_i2c = mmap.mmap(fd, PAGESIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=I2C1_BASE)
        try:
            configure_i2c_pins(mem_peri)
            # Set brightness = 0
            hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x04, 0x00])
            hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x05, 0x00])
            # Turn off backlight boost & LED strings (Reg 0x08 = 0x00)
            # Panel bias (0x09) and HWEN remain active so MIPI DSI display link stays awake
            hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x08, 0x00])
            with open(STATE_FILE, "w") as f:
                f.write("off\n")
            print("Backlight turned OFF (Screen dark, power saved, panel active)")
        finally:
            mem_i2c.close()
            mem_peri.close()
    finally:
        os.close(fd)

def set_brightness(pct):
    check_root()
    pct = max(0, min(100, int(pct)))
    # 11-bit code: 0 to 2047
    # LM36274 register 0x04 has lower 3 bits (val & 0x07)
    # LM36274 register 0x05 has upper 8 bits (val >> 3)
    val = int(pct * 2047 / 100)
    lsb = val & 0x07
    msb = (val >> 3) & 0xff
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        mem_peri = mmap.mmap(fd, PAGESIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PINCTRL_PERI_BASE)
        mem_i2c = mmap.mmap(fd, PAGESIZE, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=I2C1_BASE)
        try:
            configure_i2c_pins(mem_peri)
            hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x04, lsb])
            hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x05, msb])
            if pct > 0:
                hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x08, 0x1f])
                with open(STATE_FILE, "w") as f:
                    f.write("on\n")
                print(f"Brightness set to {pct}% ({val}/2047)")
            else:
                hw_i2c_write(mem_i2c, LM36274_I2C_ADDR, [0x08, 0x00])
                with open(STATE_FILE, "w") as f:
                    f.write("off\n")
                print("Brightness set to 0% (Backlight disabled)")
        finally:
            mem_i2c.close()
            mem_peri.close()
    finally:
        os.close(fd)

def turn_on():
    set_brightness(100)

def show_status():
    check_root()
    is_bl_on, is_panel_rst, gpg2 = get_hardware_state()
    pwr_str = "Enabled" if is_bl_on else "Disabled"
    state_str = "ON (Illuminated)" if is_bl_on else "OFF (Powered down)"
    panel_str = "Running" if is_panel_rst else "In Reset (Error)"
    print(f"Display State:   {state_str}")
    print(f"Backlight Power: {pwr_str}")
    print(f"Panel Controller:{panel_str}")
    print(f"Hardware Lines:  gpg2={hex(gpg2)} (bl_en={'1' if is_bl_on else '0'}, rst={'1' if is_panel_rst else '0'})")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd in ("0", "off", "stop", "blank"):
        turn_off()
    elif cmd in ("1", "on", "start", "unblank"):
        turn_on()
    elif cmd in ("status", "state", "info"):
        show_status()
    elif cmd in ("brightness", "set", "brt"):
        if len(sys.argv) < 3:
            print("Usage: a21s-display brightness <1-100>", file=sys.stderr)
            sys.exit(1)
        try:
            val = int(sys.argv[2])
            set_brightness(val)
        except ValueError:
            print(f"Invalid percentage: '{sys.argv[2]}'. Must be 0-100.", file=sys.stderr)
            sys.exit(1)
    elif cmd.isdigit():
        set_brightness(int(cmd))
    elif cmd in ("toggle", "switch"):
        check_root()
        is_bl_on, _, _ = get_hardware_state()
        if is_bl_on:
            turn_off()
        else:
            turn_on()
    else:
        print(f"Unknown command: '{cmd}'. Use: on, off, status, toggle", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

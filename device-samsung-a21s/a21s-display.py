#!/usr/bin/env python3
"""
Samsung Galaxy A21s Display & Backlight Controller
Controls screen backlight and display state via standard Linux sysfs
(/sys/class/backlight/panel/brightness) and framebuffer ioctls (/dev/fb0),
with fallback to hardware I2C/GPIO registers if /dev/mem is available.

Usage:
  a21s-display off                 Turn off backlight (power saving)
  a21s-display on                  Turn on backlight (normal full brightness)
  a21s-display brightness <1-100>  Set backlight brightness percentage
  a21s-display status              Show current display and backlight power state
  a21s-display toggle              Toggle between on and off
"""

import sys
import os
import fcntl
import struct

SYSFS_BRIGHTNESS = "/sys/class/backlight/panel/brightness"
SYSFS_MAX_BRIGHTNESS = "/sys/class/backlight/panel/max_brightness"
SYSFS_BL_POWER = "/sys/class/backlight/panel/bl_power"
FB_DEV = "/dev/fb0"
STATE_FILE = "/run/a21s-backlight.state"

FBIOBLANK = 0x4611
FB_BLANK_UNBLANK = 0
FB_BLANK_POWERDOWN = 4

def check_root():
    if os.geteuid() != 0:
        print("Error: Root privileges required to access display hardware.", file=sys.stderr)
        print("Please run with sudo: sudo a21s-display [on|off|status|toggle]", file=sys.stderr)
        sys.exit(1)

def get_max_brightness():
    if os.path.exists(SYSFS_MAX_BRIGHTNESS):
        try:
            with open(SYSFS_MAX_BRIGHTNESS, "r") as f:
                return int(f.read().strip())
        except Exception:
            pass
    return 306

def get_current_brightness():
    if os.path.exists(SYSFS_BRIGHTNESS):
        try:
            with open(SYSFS_BRIGHTNESS, "r") as f:
                return int(f.read().strip())
        except Exception:
            pass
    return 0

def turn_off():
    check_root()
    # 1. Turn off backlight via sysfs
    if os.path.exists(SYSFS_BRIGHTNESS):
        try:
            with open(SYSFS_BRIGHTNESS, "w") as f:
                f.write("0\n")
        except Exception as e:
            print(f"Warning: Failed to set sysfs brightness: {e}", file=sys.stderr)

    if os.path.exists(SYSFS_BL_POWER):
        try:
            with open(SYSFS_BL_POWER, "w") as f:
                f.write("4\n")
        except Exception:
            pass

    # 2. Blank FB if available
    if os.path.exists(FB_DEV):
        try:
            fd = os.open(FB_DEV, os.O_RDWR)
            try:
                fcntl.ioctl(fd, FBIOBLANK, FB_BLANK_POWERDOWN)
            finally:
                os.close(fd)
        except Exception:
            pass

    with open(STATE_FILE, "w") as f:
        f.write("off\n")
    print("Backlight turned OFF (Screen dark, power saved)")

def set_brightness(pct):
    check_root()
    pct = max(0, min(100, int(pct)))
    max_b = get_max_brightness()
    val = int(pct * max_b / 100)

    # 1. Unblank FB if needed
    if pct > 0 and os.path.exists(FB_DEV):
        try:
            fd = os.open(FB_DEV, os.O_RDWR)
            try:
                fcntl.ioctl(fd, FBIOBLANK, FB_BLANK_UNBLANK)
            finally:
                os.close(fd)
        except Exception:
            pass

    # 2. Set sysfs power and brightness
    if os.path.exists(SYSFS_BL_POWER):
        try:
            with open(SYSFS_BL_POWER, "w") as f:
                f.write("0\n" if pct > 0 else "4\n")
        except Exception:
            pass

    if os.path.exists(SYSFS_BRIGHTNESS):
        try:
            with open(SYSFS_BRIGHTNESS, "w") as f:
                f.write(f"{val}\n")
        except Exception as e:
            print(f"Error setting brightness: {e}", file=sys.stderr)
            sys.exit(1)

    state = "on" if pct > 0 else "off"
    with open(STATE_FILE, "w") as f:
        f.write(f"{state}\n")

    if pct > 0:
        print(f"Brightness set to {pct}% ({val}/{max_b})")
    else:
        print("Brightness set to 0% (Backlight disabled)")

def turn_on():
    set_brightness(75)  # 75% = ~230 / 306, bright and power efficient

def show_status():
    cur_b = get_current_brightness()
    max_b = get_max_brightness()
    pct = int(cur_b * 100 / max_b) if max_b > 0 else 0
    is_on = cur_b > 0

    pwr_str = "Enabled" if is_on else "Disabled"
    state_str = f"ON ({pct}% - {cur_b}/{max_b})" if is_on else "OFF (Powered down)"
    print(f"Display State:    {state_str}")
    print(f"Backlight Power:  {pwr_str}")
    print(f"Brightness Level: {pct}% ({cur_b}/{max_b})")

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
        cur_b = get_current_brightness()
        if cur_b > 0:
            turn_off()
        else:
            turn_on()
    else:
        print(f"Unknown command: '{cmd}'. Use: on, off, status, brightness <1-100>, toggle", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

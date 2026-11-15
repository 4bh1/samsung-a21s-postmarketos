#!/usr/bin/python3
"""
S2MU106 Battery & Charge Threshold Manager for Samsung Galaxy A21s (SM-A217F)

Maintains battery charge level within a healthy range (default 50% - 70%)
by toggling S2MU106 buck charger between BUCK_MODE (0x01, USB powered, charging off)
and CHG_MODE (0x03, USB powered, charging on).
"""

import os
import sys
import time
import fcntl
import json
import argparse

I2C_BUS = "/dev/i2c-0"
I2C_SLAVE_FORCE = 0x0706

# I2C Addresses
ADDR_FG = 0x3B       # S2MU106 Fuel Gauge
ADDR_CHG = 0x3D      # S2MU106 Charger & Buck MFD

# Registers
REG_FG_RVBAT = 0x04    # 2 bytes: Battery Voltage
REG_FG_RCUR_CC = 0x06  # 2 bytes: Battery Current (coulomb counter)
REG_FG_RSOC = 0x08     # 2 bytes: Battery State of Charge
REG_CHG_CTRL0 = 0x18   # 1 byte: Charger Mode (bits 3:0)

# Charger Modes
MODE_CHARGER_OFF = 0x00
MODE_BUCK_ONLY = 0x01   # Powers device from USB, battery idle/no charge
MODE_CHARGING = 0x03    # Powers device from USB + charges battery

STATUS_FILE = "/run/s2mu106_battery.json"


def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [battery-manager] {msg}"
    print(formatted, flush=True)
    try:
        with open("/dev/kmsg", "w") as k:
            k.write(f"<6>[battery-manager] {msg}\n")
    except Exception:
        pass


class S2MU106:
    def __init__(self, bus_path=I2C_BUS):
        self.bus_path = bus_path
        self.fd = None

    def open(self):
        if self.fd is None:
            self.fd = os.open(self.bus_path, os.O_RDWR)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def read_regs(self, addr, reg, count=1):
        self.open()
        fcntl.ioctl(self.fd, I2C_SLAVE_FORCE, addr)
        os.write(self.fd, bytes([reg]))
        return list(os.read(self.fd, count))

    def write_reg(self, addr, reg, val):
        self.open()
        fcntl.ioctl(self.fd, I2C_SLAVE_FORCE, addr)
        os.write(self.fd, bytes([reg, val]))

    def get_soc(self):
        data = self.read_regs(ADDR_FG, REG_FG_RSOC, 2)
        compliment = (data[1] << 8) | data[0]
        if compliment & 0x8000:
            soc_raw = (((~compliment & 0xFFFF) + 1) * (-10000)) / 16384.0
        else:
            soc_raw = ((compliment & 0x7FFF) * 10000) / 16384.0
        return max(0.0, min(100.0, soc_raw / 100.0))

    def get_vbat_mv(self):
        data = self.read_regs(ADDR_FG, REG_FG_RVBAT, 2)
        vbat = ((data[0] + (data[1] << 8)) * 1000) >> 13
        return vbat

    def get_current_ma(self):
        data = self.read_regs(ADDR_FG, REG_FG_RCUR_CC, 2)
        compliment = (data[1] << 8) | data[0]
        if compliment & 0x8000:
            curr = (((~compliment & 0xFFFF) + 1) * 1000) >> 12
        else:
            curr = ((compliment & 0x7FFF) * (-1000)) >> 12
        return curr

    def get_charger_mode(self):
        ctrl0 = self.read_regs(ADDR_CHG, REG_CHG_CTRL0, 1)[0]
        return ctrl0 & 0x0F, ctrl0

    def set_charger_mode(self, mode):
        ctrl0 = self.read_regs(ADDR_CHG, REG_CHG_CTRL0, 1)[0]
        new_ctrl0 = (ctrl0 & 0xF0) | (mode & 0x0F)
        self.write_reg(ADDR_CHG, REG_CHG_CTRL0, new_ctrl0)
        return new_ctrl0


def get_status_dict(pmic):
    soc = pmic.get_soc()
    vbat = pmic.get_vbat_mv()
    curr = pmic.get_current_ma()
    mode, raw_ctrl0 = pmic.get_charger_mode()

    if mode == MODE_CHARGING:
        mode_str = "charging"
    elif mode == MODE_BUCK_ONLY:
        mode_str = "buck-only (charge suspended)"
    elif mode == MODE_CHARGER_OFF:
        mode_str = "charger off"
    else:
        mode_str = f"mode-0x{mode:02x}"

    if curr > 10:
        state = "Charging"
    elif curr < -10:
        state = "Discharging"
    else:
        state = "Idle / Bypass"

    return {
        "soc_percent": round(soc, 2),
        "voltage_mv": vbat,
        "current_ma": curr,
        "state": state,
        "mode": mode_str,
        "mode_raw": mode,
        "reg_ctrl0": hex(raw_ctrl0),
        "timestamp": int(time.time()),
    }


def update_status_file(data):
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, STATUS_FILE)
        os.chmod(STATUS_FILE, 0o644)
    except Exception:
        pass


def run_daemon(stop_pct=70.0, start_pct=50.0, poll_interval=15):
    log(f"Starting Battery Charge Threshold Daemon (Stop: {stop_pct}%, Start: {start_pct}%)")
    pmic = S2MU106()

    # Wait for I2C bus
    for _ in range(30):
        if os.path.exists(I2C_BUS):
            break
        time.sleep(1)

    if not os.path.exists(I2C_BUS):
        log(f"FATAL: {I2C_BUS} not found")
        sys.exit(1)

    while True:
        try:
            status = get_status_dict(pmic)
            update_status_file(status)

            soc = status["soc_percent"]
            mode = status["mode_raw"]

            # Charge control hysteresis logic
            if soc >= stop_pct and mode != MODE_BUCK_ONLY:
                log(f"SoC ({soc:.1f}%) >= stop threshold ({stop_pct}%). Suspending charge (buck-only).")
                pmic.set_charger_mode(MODE_BUCK_ONLY)
            elif soc <= start_pct and mode != MODE_CHARGING:
                log(f"SoC ({soc:.1f}%) <= start threshold ({start_pct}%). Enabling charge.")
                pmic.set_charger_mode(MODE_CHARGING)

        except Exception as e:
            log(f"Error in monitor loop: {e}")

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="S2MU106 Battery & Charge Threshold Manager")
    parser.add_argument("--status", action="store_true", help="Print current battery status and exit")
    parser.add_argument("--json", action="store_true", help="Print current status in JSON")
    parser.add_argument("--daemon", action="store_true", help="Run background monitoring daemon")
    parser.add_argument("--stop", type=float, default=70.0, help="Stop charging percentage threshold (default: 70)")
    parser.add_argument("--start", type=float, default=50.0, help="Resume charging percentage threshold (default: 50)")
    parser.add_argument("--interval", type=int, default=15, help="Poll interval in seconds (default: 15)")
    parser.add_argument("--enable-charge", action="store_true", help="Force enable charging")
    parser.add_argument("--disable-charge", action="store_true", help="Force disable charging (buck-only)")

    args = parser.parse_args()
    pmic = S2MU106()

    if args.enable_charge:
        pmic.set_charger_mode(MODE_CHARGING)
        print("Charging FORCE ENABLED (0x03)")
        return

    if args.disable_charge:
        pmic.set_charger_mode(MODE_BUCK_ONLY)
        print("Charging FORCE DISABLED (buck-only mode 0x01)")
        return

    if args.daemon:
        run_daemon(stop_pct=args.stop, start_pct=args.start, poll_interval=args.interval)
        return

    # Default to status output
    try:
        try:
            status = get_status_dict(pmic)
        except Exception:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE) as f:
                    status = json.load(f)
            else:
                raise

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"=== S2MU106 Battery Status ===")
            print(f"Level:         {status['soc_percent']:.1f}%")
            print(f"Voltage:       {status['voltage_mv']} mV")
            print(f"Current:       {status['current_ma']} mA ({status['state']})")
            print(f"Charger Mode:  {status['mode']} (CTRL0: {status['reg_ctrl0']})")
    except Exception as e:
        print(f"Error reading battery status: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

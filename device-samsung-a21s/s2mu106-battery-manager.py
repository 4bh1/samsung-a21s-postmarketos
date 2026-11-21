#!/usr/bin/python3
"""
S2MU106 Battery & Charge Threshold Manager for Samsung Galaxy A21s (SM-A217F)

Maintains battery charge level within a healthy range (default 50% - 70%)
by toggling S2MU106 buck charger between BUCK_MODE (0x01, USB powered, charging off)
and CHG_MODE (0x03, USB powered, charging on).

Also maintains MUIC (0x3E) attach detection and Charger (0x3D) input current
limits (2.0A) and fast-charge current (1.4A) so the phone charges properly
even after cable reconnects and on standard 5V wall chargers.
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
ADDR_CCIC = 0x3C     # S2MU106 CCIC (Type-C)
ADDR_CHG = 0x3D      # S2MU106 Charger & Buck MFD
ADDR_MUIC = 0x3E     # S2MU106 MUIC & Analog Switch

# Registers
REG_FG_RVBAT = 0x04    # 2 bytes: Battery Voltage
REG_FG_RCUR_CC = 0x06  # 2 bytes: Battery Current (coulomb counter)
REG_FG_RSOC = 0x08     # 2 bytes: Battery State of Charge

REG_CHG_STATUS0 = 0x0E # 1 byte: WCIN & CHGIN status (VBUS detection)
REG_CHG_STATUS1 = 0x0F # 1 byte: Charger fault status (bit 4: WD_SUSPEND)
REG_CHG_CTRL0 = 0x18   # 1 byte: Charger Mode (bits 3:0)
REG_CHG_CTRL1 = 0x19   # 1 byte: Input Current Limit
REG_CHG_CTRL3 = 0x1B   # 1 byte: Fast Charge Current
REG_CHG_CTRL12 = 0x24  # 1 byte: Watchdog timer control (bit 4: enable, bit 0: kick)

# Hardware settings
INPUT_CURRENT_2000MA = 0x73 # 2.0A input limit
FAST_CHARGE_1400MA = 0x38   # 1.4A fast charge current

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
        # In S2MU106 fuel gauge hardware:
        # Negative two's complement indicates current flowing INTO battery (Charging).
        # Positive indicates current drawn OUT of battery (Discharging).
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

    def kickstart_charging(self):
        """
        Triggers rising edge (0x01 -> 0x03) on S2MU106 charger enable bit
        and clears watchdog timer suspend state.
        The S2MU106 state machine requires this transition to switch from
        Standby / Bypass idle into active Constant Current (CC) charging.
        """
        try:
            # Kick and disable watchdog
            self.write_reg(ADDR_CHG, REG_CHG_CTRL12, 0x01)
            self.write_reg(ADDR_CHG, REG_CHG_CTRL12, 0x00)
        except Exception:
            pass
        self.set_charger_mode(MODE_BUCK_ONLY)
        time.sleep(0.3)
        self.set_charger_mode(MODE_CHARGING)

    def get_charger_status(self):
        try:
            st = self.read_regs(ADDR_CHG, REG_CHG_STATUS0, 6)
            # st[0] is STATUS0 (0x0E): bits 2:0 are CHGIN status (5 = valid VBUS)
            # st[1] is STATUS1 (0x0F): bits 7:4 are Fault status (1 = WD_SUSPEND, 2 = WD_RST)
            vbus_active = (st[0] & 0x07) != 0
            fault_wd = ((st[1] >> 4) & 0x0F) in [1, 2]
            return vbus_active, fault_wd, st
        except Exception:
            return False, False, []

    def maintain_hardware(self, mode=MODE_CHARGING):
        """
        Actively maintains MUIC VBUS attach comparator, CCIC Type-C termination,
        disables hardware charger watchdog timer, and maintains current limits
        so charging stays functional across replugs and wall chargers.
        """
        # 1. Maintain MUIC attach detection (0x09 - 0x25)
        muic_regs = {
            0x09: 0xFC, 0x0A: 0x7A, 0x0B: 0xFF, 0x0C: 0xFF,
            0x0D: 0x7F, 0x0E: 0xFF, 0x12: 0x38, 0x13: 0x60,
            0x15: 0x40, 0x16: 0x38, 0x17: 0x30, 0x18: 0x62,
            0x19: 0x70, 0x1D: 0xD0, 0x20: 0x22, 0x21: 0xF0,
            0x24: 0xA3, 0x25: 0x30
        }
        for r, val in muic_regs.items():
            try:
                cur = self.read_regs(ADDR_MUIC, r, 1)[0]
                if cur != val:
                    self.write_reg(ADDR_MUIC, r, val)
            except Exception:
                pass

        # 2. Maintain CCIC Type-C Sink mode (0x03 - 0x07)
        ccic_regs = {
            0x03: 0x78, 0x04: 0x90, 0x05: 0x77, 0x06: 0x88, 0x07: 0x46
        }
        for r, val in ccic_regs.items():
            try:
                cur = self.read_regs(ADDR_CCIC, r, 1)[0]
                if cur != val:
                    self.write_reg(ADDR_CCIC, r, val)
            except Exception:
                pass

        # 3. Maintain Charger limits and mode, and keep watchdog disabled
        try:
            # Check and disable hardware watchdog timer (reg 0x24)
            cur_wdt = self.read_regs(ADDR_CHG, REG_CHG_CTRL12, 1)[0]
            if cur_wdt != 0x00:
                self.write_reg(ADDR_CHG, REG_CHG_CTRL12, 0x01) # kick
                self.write_reg(ADDR_CHG, REG_CHG_CTRL12, 0x00) # disable

            cur_in = self.read_regs(ADDR_CHG, REG_CHG_CTRL1, 1)[0]
            if cur_in != INPUT_CURRENT_2000MA:
                self.write_reg(ADDR_CHG, REG_CHG_CTRL1, INPUT_CURRENT_2000MA)

            cur_fc = self.read_regs(ADDR_CHG, REG_CHG_CTRL3, 1)[0]
            if cur_fc != FAST_CHARGE_1400MA:
                self.write_reg(ADDR_CHG, REG_CHG_CTRL3, FAST_CHARGE_1400MA)

            self.set_charger_mode(mode)
        except Exception:
            pass


def get_status_dict(pmic):
    soc = pmic.get_soc()
    vbat = pmic.get_vbat_mv()
    curr = pmic.get_current_ma()
    mode, raw_ctrl0 = pmic.get_charger_mode()
    vbus_ok, fault_wd, raw_status = pmic.get_charger_status()

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
        "vbus_connected": vbus_ok,
        "watchdog_suspended": fault_wd,
        "reg_ctrl0": hex(raw_ctrl0),
        "reg_status": [hex(b) for b in raw_status] if raw_status else [],
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

    # Initial hardware initialization
    pmic.maintain_hardware(MODE_CHARGING)

    while True:
        try:
            status = get_status_dict(pmic)
            update_status_file(status)

            soc = status["soc_percent"]
            mode = status["mode_raw"]

            target_mode = mode
            if soc >= stop_pct and mode != MODE_BUCK_ONLY:
                log(f"SoC ({soc:.1f}%) >= stop threshold ({stop_pct}%). Suspending charge (buck-only).")
                target_mode = MODE_BUCK_ONLY
            elif soc <= start_pct and mode != MODE_CHARGING:
                log(f"SoC ({soc:.1f}%) <= start threshold ({start_pct}%). Enabling charge.")
                target_mode = MODE_CHARGING

            # Maintain hardware registers and charging state continuously
            pmic.maintain_hardware(target_mode)

            # If charging is intended, and either:
            # - Charger watchdog timed out (fault_wd), OR
            # - VBUS is present but charging is idling (< 25 mA)
            # kickstart the CC charge state machine
            if target_mode == MODE_CHARGING:
                if status.get("watchdog_suspended") or (status.get("vbus_connected") and status.get("current_ma", 0) < 25):
                    log("Kickstarting CC charging (clearing watchdog/idle standby).")
                    pmic.kickstart_charging()

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
        pmic.maintain_hardware(MODE_CHARGING)
        print("Charging FORCE ENABLED (0x03) with 2.0A input / 1.4A fast-charge")
        return

    if args.disable_charge:
        pmic.maintain_hardware(MODE_BUCK_ONLY)
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
            vbus_str = "Connected" if status.get("vbus_connected") else "Disconnected / 0V"
            print(f"=== S2MU106 Battery Status ===")
            print(f"Level:          {status['soc_percent']:.1f}%")
            print(f"Voltage:        {status['voltage_mv']} mV")
            print(f"Current:        {status['current_ma']} mA ({status['state']})")
            print(f"Charger Mode:   {status['mode']} (CTRL0: {status['reg_ctrl0']})")
            print(f"VBUS Power:     {vbus_str}")
    except Exception as e:
        print(f"Error reading battery status: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

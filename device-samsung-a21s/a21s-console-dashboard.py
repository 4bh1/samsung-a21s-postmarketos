#!/usr/bin/env python3
"""
Samsung Galaxy A21s Framebuffer & Console System Status Dashboard
postmarketOS on Exynos 850 (Linux 4.19 downstream)

Renders real-time system performance and hardware statistics directly to
the display framebuffer (/dev/fb0) and virtual console (/dev/tty0).
Features flicker-free double buffering, automatic display unblanking,
backlight management, and monochromatic black-and-white console styling.
"""

import base64
import datetime
import fcntl
import mmap
import os
import signal
import socket
import struct
import subprocess
import sys
import time
import zlib

# Framebuffer ioctls
FBIOGET_VSCREENINFO = 0x4600
FBIOPUT_VSCREENINFO = 0x4601
FBIOPAN_DISPLAY     = 0x4606
FBIOBLANK           = 0x4611
S3CFB_SET_VSYNC_INT = 0x400446CE

FB_BLANK_UNBLANK    = 0
FB_DEV              = "/dev/fb0"
BACKLIGHT_BRIGHT    = "/sys/class/backlight/panel/brightness"
BACKLIGHT_POWER     = "/sys/class/backlight/panel/bl_power"

# Embedded 8x16 PSF console bitmap font (95 ASCII glyphs, 32-126)
FONT_B64 = (
    "eNqNV71rI0cUX0zYahFOt+SM06S4IsXiBHkJixyO/AtpUi2+sLliCK4cQYa9swv/D3ZpSOPyeoOwYSqh"
    "UgikCFVScxyqZBVmNu/N55u1DvJ05va3783M+36zUdSm+uKfi4v764uL2uBm2jSPq6aprQSTQDzft3g/"
    "5xSmRbFardK0cLiGxR5rkVQ/NYpWj3gAknpZVG/eVIXnP17f318/Gv5h55uj/hCoHxlhoCKFAzQ++eEk"
    "AzpbLzR+//b9W6A/VsuBOTydFqtiauQ/DBbrrdyuF4MPCu/FncOe7B124j2nfpqmtVU4qjTB/2b/6XT6"
    "9yskBbkocyYEyxPBiVfRZa39aoqRrHqK/IHwKpFJSjbLSllmNGaDwUAS+JpJ9trD/TznXEqiC+e5j1eL"
    "IDYFKmP0AVO/CwUY7K7+tLZcPAx4HF8Jbi14EEmaleJKo5yx/HwG8TrXumdZGWwHsorSxBiXJopSb2FV"
    "NEVFVfTRJu/IgkjusMut2ItRPxPvCKM1HmPEjFzeNxGITEC1uJAOx0Ucxza8yUHBhhIUPjRHQzCeCT8v"
    "AQsggyWs1zbb/YBF+Phcw/qkH2hODDbYmqvUA6/FvoTVP0uKhzJu/4TEV72Yz+ezAbfZAg6RqJDGz5AB"
    "HDP+2dbbA1g4eDAFGm2ZLgi2NfZVp+/678rTSga4LNdk/VyI6ieN8SR1nDmvMAVg+8WhygZf70s4qt+H"
    "Q5car0tF7jzxWcox2U8sN3I+8lj5mvhb2Vd6/Qx/POdJx/HRxqXjl3kSu/V1/Vugr2jtbxCzBac2H4/l"
    "Z2Yxg2rkzOqn25nfT4orDN6Dzb8iM2T7KXSws/zA9asiMVTYaEZfokaX24v3/YS7eo0WZdlXIfbtjAtI"
    "AGvfAZzEhl5e8SXhd4+yPurr8jk6R/EhT1RIYX92Xnn/Ql7m1J9xHHViRZVKOZDXCWDk81a+AH2S4OCx"
    "t3tmWrbXj8TH8blLAaufLenZeeXzw/R41973s+wZzeseOL5aTvxhEoBgTADmMctzGiedMXWc2JIaYj81"
    "8e+AqWdobyeYF25+IA9l0jNty+xFeFWF2+1IPesVw1B/7MM0nrA4zI9hmC/QbQKcg92BvM8fdR7uF+SL"
    "CPMH9wv4VRTkRwqTgWKUp1j4hmbUCTDMVd2gXP/A/Ol268nkTw16kNwS/TFy9gf5I8J80vp6nPWHgT+R"
    "H+SHIPHuI+RB/xBRq5+g/0bzzdLgnP1eqha41P35Kz4aYfYvl/xnml82vTqvUjU+04nOD5wLND4Y78C/"
    "wKf2IA70hwQj9QXINVyTX4z16DjC+0BErkYwBzMcr27+XX68+3h3dxncnrD8zTRbnFYMlJhBV+x5XI1u"
    "TrSIGm3qEuOWd9mEdcl2gNhEP379S/j79S78/ftX+Et309Y+lINwfnIR4iRuz1d+eXN7e3tj7O0ibeJN"
    "9wtk3BHyN7Gk9xwsL38bi/TtOLwxbVv6f0uuUUhNe1K05cOeEzXt9Z4PGUHyC1Bgv9L/ODsJTjvJjgP7"
    "nqKmNbeeAv6xlzd8J2/WP1G+uW4Z//+Yfh/31ND195mNu89AtYf9QYQ429U/SP1AfynofIJuFeCohW0+"
    "tfzv/N20KKKfUYiN121wstb54TIs51a/ifDbajIEPDT2B3zX3Zw8RJT0B4dov6rsfB3o+c3pvF1ryPV8"
    "BX2Cfgfni9b5YT9M3Ao1L8Hf9gJVhJnpPzd23IRk9PLzon55XYLNFtlp9xPtN//j+y+FvdKXHyTqhq/a"
    "IaHdtzVy+c+Dq07E8WOE9MqiStKjUPVa086N/wO2lwOa"
)

# Colors: 32-bit BGRA/RGBA on Exynos DECON
# Monochromatic high contrast: Pure Black & Pure White
PIXEL_BLACK = b"\x00\x00\x00\x00"
PIXEL_WHITE = b"\xff\xff\xff\x00"

# Precompute 2x scale row expansion LUT (256 entries -> 64 bytes each = 16 pixels)
ROW_LUT = []
for b in range(256):
    row_bytes = bytearray()
    for bit in range(7, -1, -1):
        p = PIXEL_WHITE if (b & (1 << bit)) else PIXEL_BLACK
        row_bytes.extend(p * 2)
    ROW_LUT.append(bytes(row_bytes))

FONT_DATA = zlib.decompress(base64.b64decode(FONT_B64))

# Screen dimensions: 720x1600 (scaled font: 16x32 -> 45 cols x 50 rows)
COLS = 45
ROWS = 50
WIDTH = 720
HEIGHT = 1600
PITCH = WIDTH * 4
FRAME_BYTES = PITCH * HEIGHT
TOP_PAD_ROWS = 2  # Clears Galaxy A21s camera hole-punch at top-left

running = True

def handle_signal(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def unblank_and_enable_display(fd):
    """Wake up Exynos DECON display controller and backlight"""
    try:
        fcntl.ioctl(fd, FBIOBLANK, FB_BLANK_UNBLANK)
    except Exception:
        pass
    try:
        fcntl.ioctl(fd, S3CFB_SET_VSYNC_INT, struct.pack("I", 1))
    except Exception:
        pass

    # Ensure backlight is active (default 220 out of 306 max)
    if os.path.exists(BACKLIGHT_BRIGHT):
        try:
            with open(BACKLIGHT_BRIGHT, "r") as f:
                cur = int(f.read().strip())
            if cur < 100:
                with open(BACKLIGHT_BRIGHT, "w") as f:
                    f.write("220\n")
        except Exception:
            pass
    if os.path.exists(BACKLIGHT_POWER):
        try:
            with open(BACKLIGHT_POWER, "w") as f:
                f.write("0\n")
        except Exception:
            pass

def make_bar(pct, width=20):
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(round((pct / 100.0) * width))
    filled = max(0, min(width, filled))
    return "[" + "|" * filled + "." * (width - filled) + "]"

class StatCollector:
    def __init__(self):
        self.prev_cpu_total = 0
        self.prev_cpu_idle = 0
        self.heartbeat_counter = 0

    def get_cpu_usage(self):
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = [float(x) for x in line.split()[1:8]]
            idle = parts[3] + parts[4]
            total = sum(parts)
            diff_total = total - self.prev_cpu_total
            diff_idle = idle - self.prev_cpu_idle
            self.prev_cpu_total = total
            self.prev_cpu_idle = idle
            if diff_total > 0:
                usage = (1.0 - diff_idle / diff_total) * 100.0
                return max(0.0, min(100.0, usage))
        except Exception:
            pass
        return 0.0

    def get_memory(self):
        mem = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = int(parts[1].split()[0])
                        mem[k] = v
        except Exception:
            pass

        total_ram = mem.get("MemTotal", 0) // 1024
        avail_ram = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
        used_ram = total_ram - avail_ram if total_ram >= avail_ram else 0
        ram_pct = (used_ram / total_ram * 100.0) if total_ram > 0 else 0.0

        total_swap = mem.get("SwapTotal", 0) // 1024
        free_swap = mem.get("SwapFree", 0) // 1024
        used_swap = total_swap - free_swap if total_swap >= free_swap else 0
        swap_pct = (used_swap / total_swap * 100.0) if total_swap > 0 else 0.0

        return total_ram, used_ram, ram_pct, total_swap, used_swap, swap_pct

    def get_disk(self):
        try:
            st = os.statvfs("/")
            total = (st.f_blocks * st.f_frsize) / (1024 * 1024 * 1024)
            free = (st.f_bavail * st.f_frsize) / (1024 * 1024 * 1024)
            used = total - free
            pct = (used / total * 100.0) if total > 0 else 0.0
            return total, used, pct
        except Exception:
            return 0.0, 0.0, 0.0

    def get_uptime_and_load(self):
        uptime_str = "0s"
        try:
            with open("/proc/uptime", "r") as f:
                up_sec = int(float(f.readline().split()[0]))
            days = up_sec // 86400
            hours = (up_sec % 86400) // 3600
            mins = (up_sec % 3600) // 60
            secs = up_sec % 60
            if days > 0:
                uptime_str = f"{days}d {hours:02d}h {mins:02d}m"
            else:
                uptime_str = f"{hours:02d}h {mins:02d}m {secs:02d}s"
        except Exception:
            pass

        try:
            load = os.getloadavg()
            load_str = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
        except Exception:
            load_str = "N/A"

        return uptime_str, load_str

    def get_temperature(self):
        paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/power_supply/battery/temp"
        ]
        temp_c = 0.0
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        v = float(f.read().strip())
                    temp_c = v / 1000.0 if v > 1000 else v / 10.0
                    break
                except Exception:
                    pass
        return temp_c

    def get_battery(self):
        info = {
            "capacity": 0,
            "voltage": 0,
            "status": "Unknown",
            "vbus": False,
            "temp": 0.0,
        }
        bat_dir = "/sys/class/power_supply/battery"
        if os.path.exists(bat_dir):
            try:
                with open(os.path.join(bat_dir, "capacity"), "r") as f:
                    info["capacity"] = int(f.read().strip())
            except Exception:
                pass
            try:
                with open(os.path.join(bat_dir, "voltage_now"), "r") as f:
                    info["voltage"] = int(f.read().strip()) // 1000
            except Exception:
                pass
            try:
                with open(os.path.join(bat_dir, "status"), "r") as f:
                    info["status"] = f.read().strip()
            except Exception:
                pass
            try:
                with open(os.path.join(bat_dir, "temp"), "r") as f:
                    t = float(f.read().strip())
                    info["temp"] = t / 10.0 if t < 1000 else t / 1000.0
            except Exception:
                pass

        # Check VBUS / USB power
        for pwr in ["/sys/class/power_supply/sec-fuelgauge/online",
                    "/sys/class/power_supply/s2mu106-charger/online",
                    "/sys/class/power_supply/usb/online"]:
            if os.path.exists(pwr):
                try:
                    with open(pwr, "r") as f:
                        if f.read().strip() == "1":
                            info["vbus"] = True
                            break
                except Exception:
                    pass
        if not info["vbus"] and info["status"] in ("Charging", "Full"):
            info["vbus"] = True

        return info

    def get_networks(self):
        nets = []
        try:
            out = subprocess.check_output(
                ["ip", "-br", "-4", "addr", "show"],
                stderr=subprocess.DEVNULL,
                universal_newlines=True
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    iface = parts[0]
                    state = parts[1]
                    addrs = parts[2:] if len(parts) > 2 else []
                    ip_str = ", ".join(addrs) if addrs else "No IPv4"
                    nets.append((iface, state, ip_str))
        except Exception:
            pass

        # Sort so wlan and rndis/usb come first, lo comes last
        def net_sort_key(n):
            iface = n[0]
            if "wlan" in iface:
                return 0
            if "rndis" in iface or "usb" in iface:
                return 1
            if "eth" in iface:
                return 2
            if "lo" in iface:
                return 9
            return 5

        nets.sort(key=net_sort_key)
        return nets

    def check_service_running(self, pattern, service_unit=None):
        """Check if service is active via pgrep or systemctl"""
        try:
            code = subprocess.call(
                ["pgrep", "-f", pattern],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if code == 0:
                return True
        except Exception:
            pass

        if service_unit:
            try:
                code = subprocess.call(
                    ["systemctl", "is-active", "--quiet", service_unit],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if code == 0:
                    return True
            except Exception:
                pass
        return False

    def build_dashboard_lines(self):
        self.heartbeat_counter += 1
        spinners = ["*", "+", "o", "#"]
        spin = spinners[self.heartbeat_counter % len(spinners)]

        hostname = socket.gethostname()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime_str, load_str = self.get_uptime_and_load()
        cpu_pct = self.get_cpu_usage()
        cpu_temp = self.get_temperature()
        total_ram, used_ram, ram_pct, total_swap, used_swap, swap_pct = self.get_memory()
        disk_total, disk_used, disk_pct = self.get_disk()
        bat = self.get_battery()
        nets = self.get_networks()

        wdt_ok = self.check_service_running("watchdog-petter", "watchdog-petter.service")
        bat_ok = self.check_service_running("s2mu106-battery-manager", "s2mu106-battery-manager.service")
        ssh_ok = self.check_service_running("sshd", "sshd.service")

        lines = []
        # Pad top to clear camera punch-hole
        for _ in range(TOP_PAD_ROWS):
            lines.append("")

        lines.append("+-------------------------------------------+")
        lines.append("|        POSTMARKETOS SYSTEM CONSOLE        |")
        lines.append("|        Samsung Galaxy A21s (SM-A217F)     |")
        lines.append("+-------------------------------------------+")
        lines.append(f" Host:   {hostname}")
        lines.append(f" Time:   {now_str}")
        lines.append(f" Uptime: {uptime_str}   Load: {load_str}")
        lines.append("---------------------------------------------")
        lines.append(" CPU & THERMAL")
        lines.append("---------------------------------------------")
        lines.append(f" Usage:  {cpu_pct:5.1f}%  {make_bar(cpu_pct, 18)}")
        lines.append(" Cores:  8x Cortex-A55 (Exynos 850)")
        lines.append(f" Temp:   {cpu_temp:.1f} C")
        lines.append("---------------------------------------------")
        lines.append(" MEMORY & STORAGE")
        lines.append("---------------------------------------------")
        lines.append(f" RAM:    {used_ram:4d} MB / {total_ram:4d} MB ({ram_pct:.0f}%)")
        lines.append(f"         {make_bar(ram_pct, 26)}")
        if total_swap > 0:
            lines.append(f" Swap:   {used_swap:4d} MB / {total_swap:4d} MB ({swap_pct:.0f}%)")
            lines.append(f"         {make_bar(swap_pct, 26)}")
        lines.append(f" Root /: {disk_used:4.1f} GB / {disk_total:4.1f} GB ({disk_pct:.0f}%)")
        lines.append(f"         {make_bar(disk_pct, 26)}")
        lines.append("---------------------------------------------")
        lines.append(" NETWORK INTERFACES")
        lines.append("---------------------------------------------")
        if not nets:
            lines.append(" None active")
        else:
            for iface, state, ip_str in nets[:3]:
                lines.append(f" {iface:<7} [{state}]: {ip_str}")
        lines.append("---------------------------------------------")
        lines.append(" BATTERY & POWER (S2MU106)")
        lines.append("---------------------------------------------")
        bat_cap = bat['capacity']
        bat_state = bat['status']
        vbus_str = "USB Connected" if bat['vbus'] else "On Battery"
        lines.append(f" Level:   {bat_cap}%  {make_bar(bat_cap, 20)}")
        lines.append(f" State:   {bat_state} ({vbus_str})")
        lines.append(f" Voltage: {bat['voltage']} mV   Temp: {bat['temp']:.1f} C")
        lines.append("---------------------------------------------")
        lines.append(" SYSTEM SERVICES")
        lines.append("---------------------------------------------")
        lines.append(f" Watchdog: {'RUNNING (OK)' if wdt_ok else 'STOPPED'}")
        lines.append(f" Battery:  {'RUNNING (OK)' if bat_ok else 'STOPPED'}")
        lines.append(f" OpenSSH:  {'RUNNING (OK)' if ssh_ok else 'STOPPED'}")
        lines.append("---------------------------------------------")
        lines.append(f" [{spin}] Beat: {self.heartbeat_counter:<5} Refresh: 2s   Console Active")
        lines.append("+-------------------------------------------+")

        return lines

def render_frame_to_buffer(fb, buffer_y_offset, lines):
    """Render text lines into the framebuffer slice at buffer_y_offset"""
    pitch = WIDTH * 4
    start_byte = buffer_y_offset * pitch
    end_byte = start_byte + FRAME_BYTES

    # Clear buffer to pure black
    fb[start_byte:end_byte] = PIXEL_BLACK * (WIDTH * HEIGHT)

    for line_idx, line_str in enumerate(lines[:ROWS]):
        chars = [ord(c) if ord(c) < 256 else 32 for c in line_str.ljust(COLS)[:COLS]]
        char_glyphs = [FONT_DATA[c * 16 : (c + 1) * 16] for c in chars]
        for r in range(16):
            scanline = b"".join(ROW_LUT[cg[r]] for cg in char_glyphs)
            y = buffer_y_offset + line_idx * 32 + r * 2
            fb[y * pitch : (y + 1) * pitch] = scanline
            fb[(y + 1) * pitch : (y + 2) * pitch] = scanline

def update_tty0(lines):
    """Also write clean output to /dev/tty0 or /dev/console if available"""
    for dev in ["/dev/tty0", "/dev/console"]:
        if os.path.exists(dev):
            try:
                with open(dev, "w") as f:
                    f.write("\033[2J\033[H" + "\n".join(lines) + "\n")
                break
            except Exception:
                pass

def main():
    if not os.path.exists(FB_DEV):
        print(f"Error: Framebuffer device {FB_DEV} not found.", file=sys.stderr)
        sys.exit(1)

    fb_fd = os.open(FB_DEV, os.O_RDWR)
    unblank_and_enable_display(fb_fd)

    vinfo = bytearray(160)
    fcntl.ioctl(fb_fd, FBIOGET_VSCREENINFO, vinfo)
    xres, yres, vxres, vyres, xoff, yoff, bpp = struct.unpack("<7I", vinfo[:28])

    total_mmap_bytes = vxres * vyres * 4
    fb = mmap.mmap(fb_fd, total_mmap_bytes, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ, offset=0)

    collector = StatCollector()
    current_buffer = 0

    try:
        while running:
            # Alternate buffers: Buffer 0 at y=0, Buffer 1 at y=1600
            target_y = 1600 if current_buffer == 0 else 0

            lines = collector.build_dashboard_lines()

            # Render into back-buffer
            render_frame_to_buffer(fb, target_y, lines)

            # Flip buffer via FBIOPAN_DISPLAY
            struct.pack_into("<2I", vinfo, 16, 0, target_y)
            fcntl.ioctl(fb_fd, FBIOPAN_DISPLAY, vinfo)
            current_buffer = 1 if current_buffer == 0 else 0

            # Update virtual console
            update_tty0(lines)

            # 2 second sleep (interruptible)
            for _ in range(20):
                if not running:
                    break
                time.sleep(0.1)

    finally:
        fb.close()
        os.close(fb_fd)

if __name__ == "__main__":
    main()

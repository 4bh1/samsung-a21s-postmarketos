# Samsung Galaxy A21s (`SM-A217F`) — postmarketOS Device Package

> **Note:** This project is vibe coded with Google Antigravity.

This package provides the postmarketOS device integration, Systemd 262 compatibility layer, Samsung SCSC Wi-Fi firmware/services, S2MU106 battery management, and display control for the **Samsung Galaxy A21s** (`SM-A217F` / `universal3830` / Exynos 850).

---

## Hardware & Subsystem Status

| Component | Status | Implementation Details |
| :--- | :--- | :--- |
| **Init System** | **`running`** | Systemd 262 (`multi-user.target`, **0 failed units**) |
| **Boot Time** | **16.2s** | Fast startup (Kernel: 5.5s + Userspace: 10.7s) |
| **Wi-Fi (`wlan0`)** | **Working** | Dual-band 2.4 GHz & 5 GHz auto-scanning (`S5N2560`) |
| **USB Networking** | **Working** | CDC-NCM / RNDIS gadget at `172.16.42.1` |
| **SSH Daemon** | **Working** | OpenSSH on port 22 (`multi-user.target`) |
| **Battery Life / Health** | **Protected** | S2MU106 PMIC 50%–70% charge hysteresis (Buck-Only mode) |
| **Watchdog Protection** | **Stabilized** | Automated hardware petter daemon (`/dev/watchdog*`) |
| **Storage & Mounts** | **Working** | Native eMMC ext4 (`/dev/mmcblk0p37` root, `p33` boot) |
| **Screen Control** | **Working** | Low-level backlight & display control (`a21s-display`) |

---

## Installation Guides

For detailed, step-by-step instructions designed for beginners:
- 📖 [**Complete Step-by-Step Installation Guide (INSTALLATION.md)**](INSTALLATION.md)
- 🛠️ [**Comprehensive Installation Walkthrough**](docs/installation-guide.md)

### Quick Summary (Building with `pmbootstrap`):
```bash
# 1. Initialize pmbootstrap for Samsung Galaxy A21s
pmbootstrap init
# Device vendor: samsung
# Device codename: a21s
# User interface: console (or preferred)

# 2. Build the kernel and device packages
pmbootstrap build linux-samsung-a21s
pmbootstrap build device-samsung-a21s

# 3. Generate rootfs image
pmbootstrap install --ui=console

# 4. Flash to device (Download Mode)
pmbootstrap flasher flash_rootfs
pmbootstrap flasher flash_kernel
```

---

## Technical Documentation

Deep-dive architecture references are available in the [`docs/`](docs/) directory:

- 📖 [**Systemd 262 Compatibility Layer (`compat.c`)**](docs/systemd-compatibility.md): Explains how we resolved `-EUNATCH`, missing `AT_EMPTY_PATH` support in musl libc on Linux 4.19, Netlink multicast downgrades, and preserved upgrade survivability across `apk upgrade`.
- 📡 [**S5N2560 Wi-Fi Bringup Guide**](docs/wifi-bringup.md): Details extracting `mx140.bin` firmware and HCF calibration files from the stock Android `super` partition, bypassing kernel VFS restrictions, and disabling MAC randomization.
- 🔋 [**Power Management & Watchdogs**](docs/power-and-watchdogs.md): S2MU106 PMIC register-level hysteresis, eliminating battery swelling via Buck-Only mode, and defeating watchdog resets.

---

## Useful On-Device Commands

After booting postmarketOS and logging in via SSH (`ssh root@172.16.42.1`):

```bash
# Check battery level and charging mode
battery-status

# Scan Wi-Fi access points
nmcli device wifi list

# Connect to Wi-Fi
nmcli device wifi connect "SSID" password "PASSWORD"

# Verify system health
systemctl is-system-running
systemctl --failed

# Screen off (save power during headless use)
screen-off

# Screen on
screen-on
```

---

## License

MIT / GPL-2.0

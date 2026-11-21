# Samsung Galaxy A21s (`SM-A217F`) — postmarketOS Systemd & Hardware Fixes

> **Note:** This project is vibe coded with Google Antigravity.

This repository provides device packages, kernel patches, firmware blobs, and compatibility layers for running **postmarketOS** (`systemd-edge`, UI: `console`) on the **Samsung Galaxy A21s** (`SM-A217F` / `universal3830` / `exynos850`) as a high-reliability, 24/7 headless server or mobile workstation.

---

## Hardware & Subsystem Status

| Component | Status | Details |
| :--- | :--- | :--- |
| **Systemd 262** | **`running`** | Reached `multi-user.target` with **0 failed units** |
| **Boot Speed** | **16.2s** | Kernel: 5.5s + Userspace: 10.7s |
| **Wi-Fi** | **Working** | Dual-band 2.4 GHz & 5 GHz auto-scanning (`S5N2560`) |
| **USB Networking** | **Working** | RNDIS / CDC-NCM gadget at `172.16.42.1` |
| **SSH Server** | **Working** | Supervised natively under systemd port 22 |
| **Battery Life / Health** | **Protected** | S2MU106 PMIC 50%–70% charge hysteresis (Buck-Only mode) |
| **Watchdogs & Panics** | **Stabilized** | Hardware watchdog kickstarter + hung task panic disabled |
| **Storage & Mounts** | **Working** | Native eMMC ext4 (`/dev/mmcblk0p37` root, `p33` boot) |

---

## Quickstart (One-Click Installation)

If postmarketOS is already installed on your device and connected via USB (`172.16.42.1`):

```bash
git clone https://github.com/4bh1/samsung-a21s-postmarketos.git
cd samsung-a21s-postmarketos
chmod +x deploy-to-device.sh install.sh

# Deploy all compatibility fixes, firmwares, and services directly:
./deploy-to-device.sh 172.16.42.1

# Reboot into the stable environment:
ssh -F /dev/null root@172.16.42.1 'sync; reboot -f'
```

---

## Technical Documentation

Detailed architectural deep-dives and implementation details are provided in separate documentation guides:

- 📖 [**Systemd 262 Compatibility Layer (`compat.c`)**](docs/systemd-compatibility.md): How we solved `-EUNATCH`, `AT_EMPTY_PATH` libc rejections, Netlink uevent socket downgrades, and guaranteed update survival.
- 📡 [**S5N2560 Wi-Fi Bringup Guide**](docs/wifi-bringup.md): Extracting `mx140.bin` firmware from the Android `super` partition, bypassing kernel VFS restrictions, and disabling MAC randomization.
- 🔋 [**Power Management & Watchdogs**](docs/power-and-watchdogs.md): S2MU106 PMIC register-level hysteresis, eliminating battery swelling with Buck-Only mode, and defeating watchdog resets.
- 🛠️ [**Step-by-Step Installation Guide**](docs/installation-guide.md): Beginner-friendly instructions for flashing with `pmbootstrap` or patching live devices.

---

## Repository Structure

```text
.
├── README.md
├── install.sh                       # Copies packages to pmaports or triggers device deploy
├── deploy-to-device.sh              # One-click SSH deployer for live phones
├── boot-native.img                  # Verified native boot image for fastboot
├── docs/
│   ├── systemd-compatibility.md
│   ├── wifi-bringup.md
│   ├── power-and-watchdogs.md
│   └── installation-guide.md
├── compat/                          # Compatibility layer files
│   ├── compat.c                     # LD_PRELOAD interceptor source code
│   ├── libsystemd-compat-4.19.so    # Compiled aarch64 shared library
│   ├── init                         # Early init handoff script
│   ├── service-10-compat.conf       # Systemd service drop-in
│   ├── fstab                        # Storage mount configuration
│   └── watchdog-petter.py           # Dedicated watchdog daemon
├── device-samsung-a21s/             # Device package for postmarketOS
│   ├── APKBUILD
│   ├── deviceinfo
│   ├── 99-wifi.conf                 # NetworkManager Wi-Fi policy
│   ├── wlan0-init.service           # Boot Wi-Fi initialization service
│   ├── s2mu106-battery-manager.py   # Battery hysteresis daemon
│   ├── s2mu106-battery-manager.service
│   └── wifi/                        # All 18 SCSC S5N2560 firmware & config files
└── linux-samsung-a21s/              # Downstream Linux 4.19 kernel package
    ├── APKBUILD
    ├── config-samsung-a21s.aarch64
    ├── a21s.cfg
    └── *.patch
```

---

## Helpful Commands On Device

```bash
# Check battery health & charging mode
battery-status

# Scan Wi-Fi networks
nmcli device wifi list

# Connect to Wi-Fi
nmcli device wifi connect "SSID" password "PASSWORD"

# Check overall system health
systemctl is-system-running
systemctl --failed
```

---

## License

MIT / GPLv2 (for kernel patches).

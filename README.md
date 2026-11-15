# Samsung Galaxy A21s (SM-A217F) — postmarketOS Headless & Hardware Fixes

> **Note:** This project is vibe coded with Google Antigravity.

This repository provides device definitions, kernel patches, and power-management daemons for running [postmarketOS](https://postmarketos.org) on the **Samsung Galaxy A21s** (`SM-A217F` / `exynos850`) in a reliable, headless server configuration.

---

## Key Features & Fixes

### 1. Boot Hang & D-Bus Deadlock Prevention
- **Issue:** Early-boot `setup-usb-network.sh` calling `systemctl restart unudhcpd` synchronously caused a deadlock because it ran before `network.target` while `unudhcpd` depended on `network.target`.
- **Fix:** Replaced blocking systemd transactions with direct background execution (`/usr/bin/unudhcpd ... &`), ensuring the USB CDC NCM gadget (`172.16.42.1`) boots cleanly without freezing system startup.
- **Plymouth Masking:** Masked all `plymouth-*.service` units to `/dev/null` to eliminate switch-root segfaults.
- **NetworkManager Isolation:** Configured `10-unmanage-usb.conf` so NetworkManager does not reset or interfere with the USB gadget interface.

### 2. Battery Protection & Swelling Prevention
- **Daemon:** `s2mu106-battery-manager.service` runs continuously in the background monitoring State of Charge (SoC).
- **Threshold Hysteresis:**
  - **$\ge 70\%$ SoC:** Toggles S2MU106 PMIC register `0x18` (bits 3:0) into **Buck-Only mode (`0x01`)**. The phone runs entirely off USB power and suspends battery charging (0 mA current), preventing overheating and battery swelling.
  - **$\le 50\%$ SoC:** Automatically resumes charging (**`0x03`**) until 70% is reached.
- **Helper Tool:** Run `battery-status` (no `sudo` required) to view live battery voltage, current, state of charge, and PMIC register status:
  ```bash
  $ battery-status
  === S2MU106 Battery Status ===
  Level:         6.7%
  Voltage:       3694 mV
  Current:       16 mA (Charging)
  Charger Mode:  charging (CTRL0: 0x3)
  ```

### 3. Headless Console & Automated Screen-Off
- **Target:** Default target set to `multi-user.target` (no Xorg, Wayland, or display managers).
- **Power Saving:** `screen-off.service` powers off and blanks the LCD display panel immediately upon boot (`echo 4 > /sys/class/graphics/fb0/blank`).
- **Control Scripts:**
  - `screen-off`: Turns off and blanks the display panel.
  - `screen-on`: Restores framebuffer and terminal display if physical inspection is required.

### 4. Mainline Kernel Patch
- `0001-dwc3-force-gadget-softconnect.patch`:
  - Registers S2MU106 MUIC I2C driver to route USB D+/D- lines to the application processor.
  - Keeps DWC3 USB controller energized to ensure USB gadget softconnect survives cable re-plugging.

---

## Repository Structure

```
.
├── README.md
├── install.sh
├── device-samsung-a21s/
│   ├── APKBUILD
│   ├── deviceinfo
│   ├── setup-usb-network.sh
│   ├── usb-network.service
│   ├── s2mu106-battery-manager.py
│   ├── s2mu106-battery-manager.service
│   ├── s2mu106-switch.py
│   ├── s2mu106_working_state.json
│   ├── screen-off.sh
│   ├── screen-on.sh
│   ├── screen-off.service
│   ├── 10-unmanage-usb.conf
│   └── 10-console.conf
└── linux-postmarketos-exynos850/
    ├── APKBUILD
    ├── config-postmarketos-exynos850.aarch64
    └── 0001-dwc3-force-gadget-softconnect.patch
```

---

## Installation into `pmaports`

Run `install.sh` to copy or symlink these packages into your local `pmaports` tree:

```bash
./install.sh /path/to/pmaports
```

Or manually:
```bash
cp -r device-samsung-a21s ~/.local/var/pmbootstrap/cache_git/pmaports/device/testing/
cp -r linux-postmarketos-exynos850 ~/.local/var/pmbootstrap/cache_git/pmaports/device/testing/
```

Then build or flash with `pmbootstrap`:
```bash
pmbootstrap build device-samsung-a21s
pmbootstrap build linux-postmarketos-exynos850
```

---

## License
MIT / GPLv2 (for kernel patches).

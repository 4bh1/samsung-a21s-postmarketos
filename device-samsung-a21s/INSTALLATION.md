# Samsung Galaxy A21s (`SM-A217F`) — Complete Installation & Setup Guide

> **Note:** This project is vibe coded with Google Antigravity.

This guide provides step-by-step instructions so that anyone — from a beginner to an experienced developer — can install, configure, and run postmarketOS (`systemd-edge`, UI: `console`) on the **Samsung Galaxy A21s** (`SM-A217F` / `universal3830` / Exynos 850).

---

## Prerequisites

1. **Target Device:** Samsung Galaxy A21s (`SM-A217F`).
   - Unlocked bootloader (OEM unlocking enabled in Developer Options).
2. **Hardware:**
   - Reliable USB Type-C data cable.
   - Host computer running Linux (Ubuntu, Debian, Fedora, Arch, or WSL2 on Windows).
3. **Software on Host:**
   - `python3`, `git`, `openssh-client`, `tar`.
   - `pmbootstrap` (postmarketOS installation tool) or `heimdall`.

---

## Method 1: Building and Flashing from Scratch with `pmbootstrap`

Use this method if you want to generate a fresh, customized postmarketOS image for your Galaxy A21s.

### Step 1: Install `pmbootstrap`
On your host Linux machine:
```bash
# Using pipx or pip
pip install --user pmbootstrap

# Or on Alpine / postmarketOS host:
# sudo apk add pmbootstrap
```

Verify the installation:
```bash
pmbootstrap --version
```

### Step 2: Initialize `pmbootstrap`
Run the setup wizard:
```bash
pmbootstrap init
```
When prompted:
- **Work path:** Press Enter to accept the default (`~/.local/var/pmbootstrap`).
- **Channel:** Select `edge` (Systemd 262 requires edge).
- **Vendor:** `samsung`
- **Device codename:** `a21s`
- **User interface:** `console` (recommended for headless server) or your preferred UI.
- **Extra packages:** Press Enter or accept defaults.
- **Username & password:** Choose a login user and password.

### Step 3: Build Device and Kernel Packages
Ensure the A21s packages are present in your `pmaports` directory (`~/.local/var/pmbootstrap/cache_git/pmaports/device/testing/`):
```bash
# Build the downstream Linux 4.19 kernel (with native SCSC Wi-Fi driver)
pmbootstrap build linux-samsung-a21s

# Build the device configuration package (includes systemd compat layer)
pmbootstrap build device-samsung-a21s
```

### Step 4: Generate the Rootfs & Boot Images
Run the installer to construct the image:
```bash
pmbootstrap install --ui=console
```

### Step 5: Flash to the Device

#### Entering Download Mode (Odin/Heimdall Mode):
1. Power off the phone completely.
2. Hold **Volume Down + Volume Up** simultaneously.
3. While holding both buttons, connect the USB cable attached to your computer.
4. When the cyan Warning screen appears, press **Volume Up** once to enter Download Mode.

#### Flashing via `pmbootstrap`:
```bash
# Flash the rootfs to the userdata partition
pmbootstrap flasher flash_rootfs

# Flash the kernel to the boot partition
pmbootstrap flasher flash_kernel
```

Alternatively, you can extract the generated images:
```bash
pmbootstrap export
```
The files `boot.img` and `rootfs-samsung-a21s.img` will be placed in `/tmp/postmarketOS-export/` to be flashed via Heimdall or Odin.

---

## Method 2: One-Click Quick Patch on an Existing Install (Easiest)

If you already have a postmarketOS installation on your phone but are experiencing boot loops, 90-second mount timeouts, or missing Wi-Fi:

### Step 1: Connect to Phone via USB Networking
Connect the phone to your PC. Ensure the host has IP `172.16.42.2` and the phone is reachable at `172.16.42.1`:
```bash
ping -c 2 172.16.42.1
```

### Step 2: Clone the Helper Repository & Deploy
On your host PC:
```bash
git clone https://github.com/4bh1/samsung-a21s-postmarketos.git
cd samsung-a21s-postmarketos
chmod +x deploy-to-device.sh

# Deploy all fixes in one step:
./deploy-to-device.sh 172.16.42.1
```

The script automatically:
1. Compiles and installs the Systemd 262 compatibility interceptor (`libsystemd-compat-4.19.so`).
2. Configures `/etc/ld.so.preload` and systemd drop-ins.
3. Installs the early `init` wrapper and watchdog daemon (`watchdog-petter.py`).
4. Installs the S2MU106 battery management daemon (50%–70% charge threshold).
5. Deploys the 18 S5N2560 Wi-Fi firmware files to `/vendor/etc/wifi/` and disables scan MAC randomization.
6. Enables all system services.

### Step 3: Reboot
```bash
ssh -F /dev/null root@172.16.42.1 'sync; reboot -f'
```
The phone will boot cleanly into `multi-user.target` in approximately **16 seconds**!

---

## Post-Boot Verification Checklist

Once logged into your device via SSH (`ssh root@172.16.42.1`):

### 1. Verify Systemd Status
```bash
systemctl is-system-running
# Output should be: running
```

### 2. Verify No Failed Services
```bash
systemctl --failed
# Output should be: 0 loaded units listed
```

### 3. Check Battery Status & Charging Mode
```bash
battery-status
# Shows current battery voltage, SoC percentage, charge current, and mode:
# - Mode "charging": battery SoC is between 50% and 70%
# - Mode "buck_only": battery is >= 70% (running directly off USB power)
```

### 4. Scan & Connect to Wi-Fi
```bash
# List available 2.4 GHz and 5 GHz networks
nmcli device wifi list

# Connect to your Wi-Fi network
nmcli device wifi connect "Your_SSID" password "Your_Password"

# Verify IP address assignment
ip addr show wlan0
```

### 5. Control Screen Power (For Headless Server Mode)
```bash
# Turn off backlight to save power and eliminate screen burn-in
screen-off

# Turn screen back on when needed
screen-on
```

---

## Troubleshooting & FAQ

### Q: Why does systemd hang at boot for 90 seconds on `/dev/mmcblk0p33`?
**A:** Systemd 262 checks if `/dev` is a valid devtmpfs mount using `dev_is_devtmpfs()`. On Linux 4.19, `dev_is_devtmpfs()` fails because the kernel lacks `STATX_MNT_ID`. Systemd silently drops its uevent Netlink socket mask to `00000000`, causing it to never receive udev partition events. The preloaded `libsystemd-compat-4.19.so` intercepts this check and forces it to succeed, allowing immediate device recognition.

### Q: Why does Wi-Fi say `RTNETLINK answers: Invalid argument`?
**A:** Two reasons:
1. The Samsung SCSC kernel driver requires the firmware `/vendor/etc/wifi/mx140.bin` via kernel VFS. Our package provides all 18 firmware blobs extracted from stock Android.
2. NetworkManager tries to randomize MAC addresses during scanning by default. The Samsung driver does not support runtime MAC changes. `/etc/NetworkManager/conf.d/99-wifi.conf` disables scan randomization.

### Q: Will future `apk upgrade` break the fixes?
**A:** No. `libsystemd-compat-4.19.so` uses dynamic symbol resolution (`dlopen(..., RTLD_LAZY)` and `RTLD_DEFAULT`). It dynamically discovers systemd functions regardless of minor version updates. Furthermore, `/usr/bin/init` is not owned by any upstream package, so it will never be overwritten.

---

## Documentation Links

For in-depth architectural analysis:
- [Systemd 262 Compatibility Layer](docs/systemd-compatibility.md)
- [S5N2560 Wi-Fi Bringup Guide](docs/wifi-bringup.md)
- [Power Management & Watchdogs](docs/power-and-watchdogs.md)

---
*Note: This project is vibe coded with Google Antigravity.*

# Samsung Galaxy A21s — Complete Installation & Setup Guide

> [!NOTE]
> This guide is written so that anyone — even a beginner — can set up postmarketOS on the Samsung Galaxy A21s (`SM-A217F`), eliminate boot loops, unfreeze systemd, and enable Wi-Fi.

---

## Prerequisites

1. **Samsung Galaxy A21s** (`SM-A217F`).
2. USB Type-C data cable connected to your PC.
3. Linux PC (or WSL2) with standard utilities: `ssh`, `git`, `tar`.

---

## Method 1: One-Click Patch on Existing postmarketOS Install (Easiest)

If postmarketOS is already installed on your Galaxy A21s and you can reach it via USB networking (`172.16.42.1`) or SSH/Telnet:

### 1. Clone this repository on your PC:
```bash
git clone https://github.com/4bh1/samsung-a21s-postmarketos.git
cd samsung-a21s-postmarketos
```

### 2. Run the one-click deployer:
```bash
./deploy-to-device.sh 172.16.42.1
```

The script will automatically:
- Compile and install the Systemd 262 compatibility interceptor (`libsystemd-compat-4.19.so`).
- Set up `/etc/ld.so.preload` and systemd drop-ins.
- Install the early `init` wrapper and watchdog daemon.
- Install the S2MU106 battery management daemon (50%–70% charge threshold).
- Install the S5N2560 Wi-Fi firmware into `/vendor/etc/wifi/` and configure NetworkManager.
- Enable all necessary system services.

### 3. Reboot the phone:
```bash
ssh -F /dev/null root@172.16.42.1 'sync; reboot -f'
```
Wait ~16 seconds. The phone will boot straight into a clean, running multi-user environment!

---

## Method 2: Building from Scratch using `pmbootstrap`

If you are creating a new postmarketOS image for your device:

### 1. Clone this repository:
```bash
git clone https://github.com/4bh1/samsung-a21s-postmarketos.git
cd samsung-a21s-postmarketos
```

### 2. Copy packages into your `pmaports` tree:
```bash
./install.sh
```
*(Defaults to `~/.local/var/pmbootstrap/cache_git/pmaports`)*

### 3. Build the packages:
```bash
pmbootstrap build device-samsung-a21s
pmbootstrap build linux-samsung-a21s
```

### 4. Generate the installation image:
```bash
pmbootstrap install --ui=console
```

### 5. Flash to device:
Put the phone in Download Mode (Odin mode) or Fastboot mode, and flash the boot and rootfs partitions:
```bash
pmbootstrap flasher flash_rootfs
pmbootstrap flasher flash_kernel
```

---

## Method 3: Post-Boot Verification Checklist

Once logged into your device via SSH (`ssh root@172.16.42.1`):

### 1. Check Systemd Status:
```bash
systemctl is-system-running
# Expected output: running
```

### 2. Check Failed Units:
```bash
systemctl --failed
# Expected output: 0 loaded units listed
```

### 3. Check Battery & PMIC Status:
```bash
battery-status
# Shows current SoC, voltage, charge current, and mode
```

### 4. Scan Wi-Fi Networks:
```bash
nmcli device wifi list
# Lists all 2.4 GHz and 5 GHz networks in range
```

### 5. Connect to Wi-Fi:
```bash
nmcli device wifi connect "Your_Network_Name" password "Your_Password"
```

---
*Note: This project is vibe coded with Google Antigravity.*

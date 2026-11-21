#!/usr/bin/env bash
# ==============================================================================
# Samsung Galaxy A21s (SM-A217F) — One-Click postmarketOS Systemd & Wi-Fi Installer
# Vibe coded with Google Antigravity
# ==============================================================================
set -euo pipefail

TARGET_IP="${1:-172.16.42.1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_OPTS=(-F /dev/null -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5)

echo "================================================================="
echo " Samsung Galaxy A21s (SM-A217F) postmarketOS Fixes Deployer"
echo " Target Device: root@$TARGET_IP"
echo "================================================================="

if ! ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" "true" 2>/dev/null; then
    echo "ERROR: Unable to connect to root@$TARGET_IP via SSH."
    echo "Ensure the device is connected via USB and reachable at $TARGET_IP."
    exit 1
fi

echo "==> 1. Deploying Systemd 262 compatibility interceptor library..."
cat "$SCRIPT_DIR/compat/compat.c" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /etc/compat.c'
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'gcc -shared -fPIC -O2 -o /usr/lib/libsystemd-compat-4.19.so.new /etc/compat.c -ldl && mv /usr/lib/libsystemd-compat-4.19.so.new /usr/lib/libsystemd-compat-4.19.so'
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'echo "/usr/lib/libsystemd-compat-4.19.so" > /etc/ld.so.preload'

echo "==> 2. Installing systemd drop-ins..."
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'mkdir -p /etc/systemd/system.conf.d /etc/systemd/system/service.d'
cat "$SCRIPT_DIR/compat/service-10-compat.conf" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /etc/systemd/system/service.d/10-compat.conf'
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat << "EOF" > /etc/systemd/system.conf.d/10-compat.conf
[Manager]
DefaultEnvironment="LD_PRELOAD=/usr/lib/libsystemd-compat-4.19.so"
EOF'

echo "==> 3. Installing early init wrapper and watchdog petter..."
cat "$SCRIPT_DIR/compat/init" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /usr/bin/init && chmod +x /usr/bin/init'
cat "$SCRIPT_DIR/compat/watchdog-petter.py" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /usr/bin/watchdog-petter.py && chmod +x /usr/bin/watchdog-petter.py'

echo "==> 4. Configuring /etc/fstab for storage stability..."
cat "$SCRIPT_DIR/compat/fstab" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /etc/fstab'

echo "==> 5. Installing S2MU106 battery & charging daemon..."
cat "$SCRIPT_DIR/device-samsung-a21s/s2mu106-battery-manager.py" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /usr/bin/s2mu106-battery-manager.py && chmod +x /usr/bin/s2mu106-battery-manager.py'
cat "$SCRIPT_DIR/device-samsung-a21s/s2mu106-battery-manager.service" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /usr/lib/systemd/system/s2mu106-battery-manager.service'
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'ln -sf /usr/bin/s2mu106-battery-manager.py /usr/bin/battery-status'

echo "==> 6. Installing S5N2560 Wi-Fi firmware and services..."
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'mkdir -p /vendor/etc/wifi /etc/NetworkManager/conf.d /etc/udev/rules.d'
tar -cz -C "$SCRIPT_DIR/device-samsung-a21s/wifi" . | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'tar -xz -C /vendor/etc/wifi'
cat "$SCRIPT_DIR/device-samsung-a21s/99-wifi.conf" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /etc/NetworkManager/conf.d/99-wifi.conf'
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat << "EOF" > /etc/udev/rules.d/80-wifi.rules
SUBSYSTEM=="net", KERNEL=="wlan*", ENV{NM_UNMANAGED}="0"
EOF'
cat "$SCRIPT_DIR/device-samsung-a21s/wlan0-init.service" | ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'cat > /etc/systemd/system/wlan0-init.service'

echo "==> 7. Enabling system services..."
ssh "${SSH_OPTS[@]}" "root@$TARGET_IP" 'systemctl daemon-reload && systemctl enable s2mu106-battery-manager.service wlan0-init.service'

echo "================================================================="
echo " Installation Complete!"
echo " All patches, firmwares, and services have been deployed."
echo " To reboot into the fully stable environment, run:"
echo "   ssh -F /dev/null root@$TARGET_IP 'sync; reboot -f'"
echo "================================================================="

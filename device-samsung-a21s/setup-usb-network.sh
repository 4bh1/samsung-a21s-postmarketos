#!/bin/sh
set -x

CONFIGFS="/sys/kernel/config/usb_gadget"
HOST_IP="172.16.42.1"

# 1. Switch S2MU106 analog switch to AP USB
/usr/bin/python3 /usr/bin/s2mu106-switch.py || true

# 2. Ensure configfs is mounted
if ! mountpoint -q /sys/kernel/config; then
    mount -t configfs none /sys/kernel/config 2>/dev/null || true
fi

# 3. Wait up to 15 seconds for UDC to appear
UDC=""
for _ in $(seq 1 30); do
    for _udc in /sys/class/udc/*; do
        if [ -e "$_udc" ]; then
            UDC="$(basename "$_udc")"
            break
        fi
    done
    [ -n "$UDC" ] && break
    sleep 0.5
done

if [ -z "$UDC" ]; then
    echo "ERROR: No UDC found in /sys/class/udc after 15 seconds"
    exit 1
fi

echo "Found UDC: $UDC"

GADGET="$CONFIGFS/g1"

# Ensure any existing interface is brought down before changing UDC
ip link set usb0 down 2>/dev/null || true
ip link set usb1 down 2>/dev/null || true
if [ -e "$GADGET/UDC" ]; then
    echo "" > "$GADGET/UDC" 2>/dev/null || true
fi

mkdir -p "$GADGET"
echo "0x1d6b" > "$GADGET/idVendor"   # Linux Foundation
echo "0x0104" > "$GADGET/idProduct"  # Multifunction Composite Gadget

mkdir -p "$GADGET/strings/0x409"
echo "postmarketOS" > "$GADGET/strings/0x409/manufacturer"
echo "Galaxy A21s"  > "$GADGET/strings/0x409/product"
echo "postmarketOS" > "$GADGET/strings/0x409/serialnumber"

# Try ncm first, fall back to rndis
USB_FUNCTION="ncm.usb0"
if ! mkdir -p "$GADGET/functions/$USB_FUNCTION" 2>/dev/null; then
    USB_FUNCTION="rndis.usb0"
    mkdir -p "$GADGET/functions/$USB_FUNCTION"
fi

mkdir -p "$GADGET/configs/c.1/strings/0x409"
echo "USB Network" > "$GADGET/configs/c.1/strings/0x409/configuration"

# Clean out any old/competing functions from initramfs before linking NCM
rm -f "$GADGET/configs/c.1/"* 2>/dev/null || true
ln -sf "$GADGET/functions/$USB_FUNCTION" "$GADGET/configs/c.1/"

# Bind to UDC
echo "$UDC" > "$GADGET/UDC"
echo "Gadget bound to $UDC"

# Run S2MU106 switch again after UDC binding
/usr/bin/python3 /usr/bin/s2mu106-switch.py || true

# Wait for network interface to appear
IFACE=""
for _ in $(seq 1 20); do
    IFACE="$(cat "$GADGET/functions/$USB_FUNCTION/ifname" 2>/dev/null || true)"
    [ -n "$IFACE" ] && break
    sleep 0.2
done

[ -z "$IFACE" ] && IFACE="usb0"

echo "Configuring interface: $IFACE"
ip link set "$IFACE" up 2>/dev/null || true
ip addr flush dev "$IFACE" 2>/dev/null || true
ip addr add "$HOST_IP/24" dev "$IFACE" 2>/dev/null || true

# Start unudhcpd directly in background (DO NOT use systemctl restart here to avoid deadlock!)
killall -9 unudhcpd 2>/dev/null || true
if [ -x /usr/bin/unudhcpd ]; then
    /usr/bin/unudhcpd -i "$IFACE" -s "$HOST_IP" -c 172.16.42.2 &
fi

echo "USB gadget successfully configured on $IFACE ($HOST_IP)"
exit 0

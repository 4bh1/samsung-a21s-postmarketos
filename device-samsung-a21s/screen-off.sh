#!/bin/sh
TERM=linux setterm --cursor off </dev/tty1 2>/dev/null || true
TERM=linux setterm --blank force </dev/tty1 2>/dev/null || true
dmesg -n 1 2>/dev/null || true
systemctl stop getty@tty1.service 2>/dev/null || true
systemctl mask getty@tty1.service 2>/dev/null || true
dd if=/dev/zero of=/dev/fb0 bs=4096 count=1125 2>/dev/null || true
echo 1 > /sys/class/graphics/fb0/blank 2>/dev/null || true
echo "Screen turned OFF (blanked & zeroed)"

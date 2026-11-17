#!/bin/sh
echo 0 > /sys/class/graphics/fb0/blank 2>/dev/null || true
dmesg -n 4 2>/dev/null || true
TERM=linux setterm --blank poke </dev/tty1 2>/dev/null || true
TERM=linux setterm --cursor on </dev/tty1 2>/dev/null || true
systemctl unmask getty@tty1.service 2>/dev/null || true
systemctl start getty@tty1.service 2>/dev/null || true
echo "Screen turned ON (unblanked)"

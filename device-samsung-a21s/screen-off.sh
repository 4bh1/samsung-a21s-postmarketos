#!/bin/sh
echo 4 > /sys/class/graphics/fb0/blank 2>/dev/null || echo 1 > /sys/class/graphics/fb0/blank 2>/dev/null || true
setterm --blank force </dev/tty1 2>/dev/null || true
echo "Screen turned OFF (blanked)"

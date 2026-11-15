#!/bin/sh
echo 0 > /sys/class/graphics/fb0/blank 2>/dev/null || true
setterm --blank poke </dev/tty1 2>/dev/null || true
echo "Screen turned ON (unblanked)"

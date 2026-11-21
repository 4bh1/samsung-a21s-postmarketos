#!/usr/bin/env python3
import os, time

fds = []
for dev in ["/dev/watchdog", "/dev/watchdog0", "/dev/watchdog1"]:
    try:
        fd = os.open(dev, os.O_WRONLY)
        fds.append(fd)
    except Exception:
        pass

while True:
    for fd in fds:
        try:
            os.write(fd, b"\x00")
        except Exception:
            pass
    time.sleep(4)

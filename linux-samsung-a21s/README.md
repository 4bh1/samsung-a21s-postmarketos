# Samsung Galaxy A21s (`linux-samsung-a21s`) — Kernel Package

> **Note:** This project is vibe coded with Google Antigravity.

This package builds the downstream Linux 4.19 kernel for the **Samsung Galaxy A21s** (`SM-A217F` / `universal3830` / Exynos 850) with integrated Samsung SCSC Wi-Fi drivers and boot stability patches.

---

## Kernel Details

- **Kernel Version:** 4.19.325
- **Architecture:** `aarch64` (`arm64`)
- **Flavor:** `samsung-a21s`
- **Source Repository:** [samsungexynos850/android_kernel_samsung_exynos850](https://github.com/samsungexynos850/android_kernel_samsung_exynos850)
- **Commit:** `b8c71b7aecece9c67f0e840a6b074573e8041d20`

---

## Patches & Features

1. **Integrated Samsung SCSC Wi-Fi Driver (`slsi_wlan`):**
   - Built directly into the kernel image.
   - Communicates with the SCSC S5N2560 WLAN/BT chip over platform bus `119c0000.scsc_wifibt`.
   - Firmware is loaded at interface bringup from `/vendor/etc/wifi/mx140.bin`.

2. **`0001-remove-werror.patch`:**
   - Disables `-Werror` and pointer size warnings for clean compilation across newer LLVM/Clang toolchains.

3. **`0002-decon-fbops-dummy-ops.patch`:**
   - Provides dummy frame-buffer operations for the DECON display driver to prevent kernel panics when no graphical display manager is active.

4. **`0003-sec-hard-reset-disable-bug.patch`:**
   - Disables `BUG_ON()` triggers in Samsung's proprietary hard reset hook driver (`sec_hard_reset_hook.c`).

5. **DTB & DTBO Packaging:**
   - Generates DTBs with bootloader custom flag `--custom1=0xff`.
   - Generates unified `dtbo.img` from `a21s.cfg`.

---

## How to Build

To build this kernel package using `pmbootstrap`:

```bash
pmbootstrap build linux-samsung-a21s
```

---

## License

GPL-2.0-only

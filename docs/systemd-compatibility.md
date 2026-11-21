# Systemd 262 on Linux Downstream 4.19 — Deep Dive & Solutions

> [!NOTE]
> **Device Platform:** Samsung Galaxy A21s (`SM-A217F` / `universal3830` / Exynos 850)  
> **Kernel Version:** 4.19.325 (`linux-samsung-a21s`)  
> **Init System:** Systemd 262 (`systemd-edge` / Alpine Edge musl)  

---

## 1. Problem Statement

Systemd 262 relies heavily on modern Linux kernel interfaces introduced in Linux 5.x and 6.x:
1. `statx()` with `STATX_MNT_ID` / `STATX_MNT_ID_UNIQUE` (Linux 5.8+).
2. `AT_EMPTY_PATH` (0x1000) support across `fchmodat()`, `utimensat()`, and `faccessat()` (musl on 4.19 returns `EINVAL`).
3. Modern mount APIs (`fsopen`, `fsmount`, `move_mount`).
4. Modern devtmpfs mount point validation algorithms.

When running on an Android downstream Linux 4.19 kernel, these missing features lead to:
- Complete system hangs at boot when checking mount points (`path_is_mount_point_full` returning `-EUNATCH`).
- Udev failing on every block device partition tag (`Failed to update tags under /run/udev/tag/: Invalid argument`).
- Systemd PID 1 silently downgrading its Netlink socket multicast mask to `00000000`, causing 90-second device job timeouts on `/dev/mmcblk0p33` (`boot.mount` failing).
- Hang task panics and watchdog resets.

---

## 2. Root Causes & Technical Solutions

### A. Udev Tag Rejections (`fchmodat` / `utimensat` with `AT_EMPTY_PATH`)
- **Mechanism:** In systemd 262's `src/libsystemd/sd-device/device-tag.c`, `device_tag()` writes tag files under `/run/udev/tag/<tag>/<device>`. To touch and set permissions, it calls `touch_file()` which invokes:
  ```c
  fchmodat(fd, "", mode, AT_EMPTY_PATH);
  utimensat(fd, "", times, AT_EMPTY_PATH);
  ```
- **Failure:** On Linux 4.19 with musl libc, passing `AT_EMPTY_PATH` to `fchmodat` and `utimensat` returns `EINVAL` (-22).
- **Consequence:** Udev aborted database writing for major device 259 (all eMMC partitions), preventing disk symlinks (`/dev/disk/by-label/*`, `/dev/disk/by-uuid/*`) from being generated.
- **Solution:** In `compat.c`, intercepted `fchmodat()` and `utimensat()`. When `flags & AT_EMPTY_PATH` is passed and `pathname` is empty, the interceptor routes the call to `/proc/self/fd/%d`:
  ```c
  char proc_path[64];
  snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", dirfd);
  return chmod(proc_path, mode);
  ```

---

### B. PID 1 Netlink Multicast Group Downgrade (`dev_is_devtmpfs`)
- **Mechanism:** When PID 1 initializes its `sd_device_monitor` socket (protocol 15: `NETLINK_KOBJECT_UEVENT`), it evaluates:
  ```c
  if (group == MONITOR_GROUP_UDEV &&
      access("/run/udev/control", F_OK) < 0 &&
      dev_is_devtmpfs() <= 0) {
          group = MONITOR_GROUP_NONE;
  }
  ```
- **Failure:** At PID 1 initialization, `/run/udev/control` does not exist yet. `dev_is_devtmpfs()` calls `path_get_mnt_id_at(AT_FDCWD, "/dev", &id)`. Since Linux 4.19 does not support `STATX_MNT_ID`, `path_get_mnt_id_at` returns `-EUNATCH` (-49), causing `dev_is_devtmpfs()` to return `< 0`.
- **Consequence:** Systemd assumed PID 1 was running inside an unprivileged container without devtmpfs, downgrading `group` to `00000000`. PID 1 never received udev uevent notifications, leaving `dev-mmcblk0p33.device` stuck in `tentative` state until timing out after 90 seconds.
- **Solution:** Intercepted `dev_is_devtmpfs(void)` in `compat.c` to explicitly return `1`:
  ```c
  int dev_is_devtmpfs(void) {
      return 1;
  }
  ```
  PID 1 binds its netlink socket with multicast group `00000002` (`MONITOR_GROUP_UDEV`), receiving all uevents immediately.

---

### C. Mount Point Detection Fallback (`path_is_mount_point_full`)
- **Mechanism:** Systemd verifies mount points using `path_is_mount_point_full()`, which calls `xstatx_full()` requesting `XSTATX_MNT_ID_BEST`.
- **Failure:** Linux 4.19 returns `-EUNATCH` (-49) because mount IDs are unsupported.
- **Solution:** Fallback to standard POSIX `stat()` comparing device numbers (`st_dev`) and inode numbers (`st_ino`) between the target directory and its parent directory (`..`):
  ```c
  if (r == -49 && path) {
      struct stat st_path, st_parent;
      if (stat(path, &st_path) != 0) return -errno;
      if (strcmp(path, "/") == 0) return 1;
      char parent[4096];
      snprintf(parent, sizeof(parent), "%s/..", path);
      if (stat(parent, &st_parent) != 0) return -errno;
      return (st_path.st_dev != st_parent.st_dev || st_path.st_ino == st_parent.st_ino) ? 1 : 0;
  }
  ```

---

### D. Blocking Modern Mount System Calls
- **Mechanism:** In systemd 262 and modern `util-linux` mount, binaries attempt modern VFS mount system calls:
  - `fsopen` (syscall 430)
  - `fsmount` (syscall 432)
  - `move_mount` (syscall 429 / 442)
  - `fspick` (syscall 433)
- **Failure:** If these return anything other than `ENOSYS` (-38), userland hangs trying modern mount retry loops.
- **Solution:** Intercepted `syscall()`:
  - If `__progname == "mount"`, returns `ENOSYS` (-1 with `errno = ENOSYS`) to force graceful fallback to legacy `mount(2)`.
  - For service spawning, returns `EPERM` where required.

---

## 3. Update Survivability

```mermaid
flowchart LR
    A["apk upgrade / system update"] --> B["systemd upgraded (e.g. 262 -> 263)"]
    B --> C["libsystemd-shared-263.so installed"]
    C --> D["compat.c init_shared()"]
    D -->|glob scan| E["Finds newest libsystemd-shared-*.so"]
    D -->|fallback| F["RTLD_DEFAULT"]
    E & F --> G["All hooks intact without recompilation"]
```

1. **Unowned Binary:** `/usr/lib/libsystemd-compat-4.19.so` is not registered in Alpine's apk database. No system update will remove or overwrite it.
2. **Dynamic Version Binding:** Rather than hardcoding `libsystemd-shared-262.so`, `compat.c` uses `glob("/usr/lib/systemd/libsystemd-shared-*.so", ...)` and `RTLD_DEFAULT`. When systemd is upgraded, the interceptor automatically loads symbols from the new library version.
3. **Init Wrapper Safety:** `/usr/bin/init` is not owned by any package (`systemd` owns `/sbin/init`). It persists permanently across updates.

#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/stat.h>
#include <sys/mount.h>
#include <sys/syscall.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <errno.h>
#include <glob.h>

extern const char *__progname;

struct statx;

static int (*real_path_is_mount_point_full)(const char *path, const char *root, int flags) = NULL;
static int (*real_xstatx_full)(int dirfd, const char *path, int statx_flags, unsigned xstatx_flags,
                               unsigned mandatory_mask, unsigned optional_mask, uint64_t mandatory_attributes,
                               struct statx *ret) = NULL;
static int (*real_access_fd)(int fd, int mode) = NULL;
static int (*real_faccessat)(int dirfd, const char *pathname, int mode, int flags) = NULL;
static int (*real_fchmodat)(int dirfd, const char *pathname, mode_t mode, int flags) = NULL;
static int (*real_utimensat)(int dirfd, const char *pathname, const struct timespec times[2], int flags) = NULL;
static int (*real_mount)(const char *source, const char *target, const char *filesystemtype,
                         unsigned long mountflags, const void *data) = NULL;
static long (*real_syscall)(long number, ...) = NULL;

static void init_shared(void) {
    static int initialized = 0;
    if (initialized) return;
    initialized = 1;

    void *h = dlopen("/usr/lib/systemd/libsystemd-shared-262.so", RTLD_LAZY);
    if (!h) {
        glob_t gl;
        if (glob("/usr/lib/systemd/libsystemd-shared-*.so", 0, NULL, &gl) == 0 && gl.gl_pathc > 0) {
            h = dlopen(gl.gl_pathv[gl.gl_pathc - 1], RTLD_LAZY);
        }
        globfree(&gl);
    }
    if (!h) {
        h = RTLD_DEFAULT;
    }
    if (h) {
        if (!real_path_is_mount_point_full)
            real_path_is_mount_point_full = dlsym(h, "path_is_mount_point_full");
        if (!real_xstatx_full)
            real_xstatx_full = dlsym(h, "xstatx_full");
        if (!real_access_fd)
            real_access_fd = dlsym(h, "access_fd");
    }
}

int path_is_mount_point_full(const char *path, const char *root, int flags) {
    init_shared();
    int r = -49;
    if (real_path_is_mount_point_full)
        r = real_path_is_mount_point_full(path, root, flags);

    if (r >= 0)
        return r;

    if (r == -49 && path) {
        struct stat st_path, st_parent;
        if (stat(path, &st_path) != 0)
            return -errno;
        if (strcmp(path, "/") == 0)
            return 1;
        char parent[4096];
        snprintf(parent, sizeof(parent), "%s/..", path);
        if (stat(parent, &st_parent) != 0)
            return -errno;
        return (st_path.st_dev != st_parent.st_dev || st_path.st_ino == st_parent.st_ino) ? 1 : 0;
    }
    return r;
}

int xstatx_full(int dirfd, const char *path, int statx_flags, unsigned xstatx_flags,
                unsigned mandatory_mask, unsigned optional_mask, uint64_t mandatory_attributes,
                struct statx *ret) {
    init_shared();
    if (!real_xstatx_full)
        return -38;
    int r = real_xstatx_full(dirfd, path, statx_flags, xstatx_flags, mandatory_mask, optional_mask, mandatory_attributes, ret);
    if (r == -49) {
        r = real_xstatx_full(dirfd, path, statx_flags, xstatx_flags & ~0x7, mandatory_mask, optional_mask, mandatory_attributes, ret);
    }
    return r;
}

int path_is_root_at(int dirfd, const char *path) {
    struct stat st, st_root;
    if (stat("/", &st_root) != 0)
        return -errno;

    if (path && strcmp(path, "/") == 0)
        return 1;

    if (dirfd >= 0 && (!path || path[0] == 0)) {
        if (fstat(dirfd, &st) != 0)
            return -errno;
        return (st.st_dev == st_root.st_dev && st.st_ino == st_root.st_ino) ? 1 : 0;
    }

    if (fstatat(dirfd, path ? path : ".", &st, 0) != 0)
        return -errno;

    return (st.st_dev == st_root.st_dev && st.st_ino == st_root.st_ino) ? 1 : 0;
}

int access_fd(int fd, int mode) {
    if (fd < 0) return -EBADF;
    char proc_path[64];
    snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", fd);
    return access(proc_path, mode) == 0 ? 0 : -errno;
}

int faccessat(int dirfd, const char *pathname, int mode, int flags) {
    if (!real_faccessat)
        real_faccessat = dlsym(RTLD_NEXT, "faccessat");

    if (flags == 0) {
        if (real_faccessat)
            return real_faccessat(dirfd, pathname, mode, 0);
        return syscall(SYS_faccessat, dirfd, pathname, mode);
    }

    if (flags & AT_SYMLINK_NOFOLLOW) {
        struct stat st;
        if (fstatat(dirfd, pathname, &st, AT_SYMLINK_NOFOLLOW) != 0)
            return -1;
        if (mode == F_OK)
            return 0;
        if (S_ISLNK(st.st_mode))
            return 0;
        if (real_faccessat)
            return real_faccessat(dirfd, pathname, mode, flags & ~AT_SYMLINK_NOFOLLOW);
        return syscall(SYS_faccessat, dirfd, pathname, mode);
    }

    if (flags & AT_EMPTY_PATH) {
        if (!pathname || pathname[0] == 0) {
            char proc_path[64];
            snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", dirfd);
            return access(proc_path, mode);
        }
    }

    if (real_faccessat)
        return real_faccessat(dirfd, pathname, mode, flags);
    return syscall(SYS_faccessat, dirfd, pathname, mode);
}

int fchmodat(int dirfd, const char *pathname, mode_t mode, int flags) {
    if (!real_fchmodat)
        real_fchmodat = dlsym(RTLD_NEXT, "fchmodat");

    if (flags & AT_EMPTY_PATH) {
        if (!pathname || pathname[0] == '\0') {
            char proc_path[64];
            snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", dirfd);
            return chmod(proc_path, mode);
        }
    }

    if (flags == 0) {
        if (real_fchmodat)
            return real_fchmodat(dirfd, pathname, mode, 0);
        return syscall(SYS_fchmodat, dirfd, pathname, mode);
    }

    if (flags & AT_SYMLINK_NOFOLLOW) {
        struct stat st;
        if (fstatat(dirfd, pathname, &st, AT_SYMLINK_NOFOLLOW) == 0 && S_ISLNK(st.st_mode))
            return 0; /* Linux does not support changing symlink permissions */
    }

    if (real_fchmodat)
        return real_fchmodat(dirfd, pathname, mode, flags);
    return syscall(SYS_fchmodat, dirfd, pathname, mode);
}

int utimensat(int dirfd, const char *pathname, const struct timespec times[2], int flags) {
    if (!real_utimensat)
        real_utimensat = dlsym(RTLD_NEXT, "utimensat");

    if (flags & AT_EMPTY_PATH) {
        if (!pathname || pathname[0] == '\0') {
            char proc_path[64];
            snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", dirfd);
            if (real_utimensat)
                return real_utimensat(AT_FDCWD, proc_path, times, 0);
            return syscall(SYS_utimensat, AT_FDCWD, proc_path, times, 0);
        }
    }

    if (real_utimensat)
        return real_utimensat(dirfd, pathname, times, flags);
    return syscall(SYS_utimensat, dirfd, pathname, times, flags);
}

int sd_booted(void) {
    struct stat st;
    if (stat("/run/systemd/system", &st) == 0 && S_ISDIR(st.st_mode))
        return 1;
    return 0;
}

int dev_is_devtmpfs(void) {
    return 1;
}

int mount(const char *source, const char *target, const char *filesystemtype,
          unsigned long mountflags, const void *data) {
    if (!real_mount)
        real_mount = dlsym(RTLD_NEXT, "mount");

    int r = -1;
    if (real_mount)
        r = real_mount(source, target, filesystemtype, mountflags, data);
    else
        r = syscall(SYS_mount, source, target, filesystemtype, mountflags, data);

    if (r != 0 && errno == EINVAL && filesystemtype && strcmp(filesystemtype, "proc") == 0) {
        if (real_mount)
            r = real_mount(source, target, filesystemtype, mountflags, NULL);
        else
            r = syscall(SYS_mount, source, target, filesystemtype, mountflags, NULL);
    }
    return r;
}

long syscall(long number, ...) {
    if (!real_syscall)
        real_syscall = dlsym(RTLD_NEXT, "syscall");

    va_list args;
    va_start(args, number);
    long a1 = va_arg(args, long);
    long a2 = va_arg(args, long);
    long a3 = va_arg(args, long);
    long a4 = va_arg(args, long);
    long a5 = va_arg(args, long);
    long a6 = va_arg(args, long);
    va_end(args);

    if (number == 430 || number == 431 || number == 432 || number == 442) {
        if (__progname && strcmp(__progname, "mount") == 0) {
            errno = ENOSYS;
            return -1;
        }
        errno = EPERM;
        return -1;
    }

    if (real_syscall)
        return real_syscall(number, a1, a2, a3, a4, a5, a6);
    errno = ENOSYS;
    return -1;
}

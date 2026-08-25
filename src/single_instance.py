"""Prevents two copies of the app from running at once, which would
otherwise write to the same data files concurrently."""
import os


def _pid_is_running(pid):
    try:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return True  # assume running if we can't check, to be safe


def acquire(lock_file):
    """Returns True if this process may proceed, False if another live
    instance already holds the lock."""
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
        except Exception:
            old_pid = None

        if old_pid and _pid_is_running(old_pid):
            return False

    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    return True


def release(lock_file):
    try:
        os.remove(lock_file)
    except Exception:
        pass

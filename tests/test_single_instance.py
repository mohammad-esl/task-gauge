import os

import single_instance


def test_first_acquire_succeeds(tmp_path):
    lock = str(tmp_path / "test.lock")
    assert single_instance.acquire(lock) is True
    assert os.path.exists(lock)


def test_second_acquire_fails_while_first_process_alive(tmp_path):
    lock = str(tmp_path / "test.lock")
    single_instance.acquire(lock)
    assert single_instance.acquire(lock) is False


def test_release_removes_lock_file(tmp_path):
    lock = str(tmp_path / "test.lock")
    single_instance.acquire(lock)
    single_instance.release(lock)
    assert not os.path.exists(lock)


def test_release_missing_lock_is_a_noop(tmp_path):
    lock = str(tmp_path / "does_not_exist.lock")
    single_instance.release(lock)  # should not raise


def test_stale_lock_from_dead_pid_is_reclaimed(tmp_path):
    lock = str(tmp_path / "test.lock")
    with open(lock, "w") as f:
        f.write("999999999")  # a PID that (almost certainly) isn't running
    assert single_instance.acquire(lock) is True

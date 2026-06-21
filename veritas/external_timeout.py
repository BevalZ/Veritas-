"""Timeout helpers for external capability calls."""

import signal
import threading

__all__ = ["_ExternalCapabilityTimeout", "_run_with_alarm_timeout"]


class _ExternalCapabilityTimeout(BaseException):
    pass


def _run_with_alarm_timeout(func, timeout, timeout_result):
    """Bound third-party calls that may ignore socket timeouts."""
    try:
        seconds = max(1, int(timeout or 1))
    except Exception:
        seconds = 1
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        return func()

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _raise_timeout(signum, frame):
        raise _ExternalCapabilityTimeout(f"operation exceeded {seconds}s")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        return func()
    except _ExternalCapabilityTimeout:
        return timeout_result()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)

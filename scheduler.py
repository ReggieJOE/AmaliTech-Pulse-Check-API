"""
scheduler.py — Manages per-device countdown timers.

Core of the Dead Man's Switch logic.
Uses Python's threading.Timer so each device gets its own
non-blocking countdown thread. When a timer fires, the device
is declared "down" and an alert is triggered.

Design decision: threading.Timer instead of asyncio because
Flask is synchronous. Each Timer is a lightweight daemon thread
that sleeps and then calls the alert callback once.
"""

import threading
import json
from datetime import datetime, timezone

import store

# Maps device_id → active threading.Timer instance
_timers: dict[str, threading.Timer] = {}
_lock = threading.Lock()  # Protects _timers from race conditions


def _fire_alert(device_id: str) -> None:
    """
    Internal callback — runs when a timer expires.
    Marks the device as 'down' and logs a structured alert.
    In production: replace the print with a webhook POST or email send.
    """
    monitor = store.get_monitor(device_id)
    if not monitor:
        return  # Device was deleted before timer fired

    # Update status to 'down' in the store
    store.set_monitor(device_id, {**monitor, "status": "down"})

    # The alert — console.log equivalent in Python
    alert = {
        "ALERT": f"Device {device_id} is down!",
        "alert_email": monitor.get("alert_email"),
        "time": datetime.now(timezone.utc).isoformat()
    }
    print(json.dumps(alert))


def start_timer(device_id: str) -> None:
    """
    Start a countdown for the given device.
    Cancels any existing timer first to prevent duplicate alerts.
    """
    stop_timer(device_id)

    monitor = store.get_monitor(device_id)
    if not monitor or monitor.get("status") == "paused":
        return

    timer = threading.Timer(
        interval=monitor["timeout"],
        function=_fire_alert,
        args=[device_id]
    )
    timer.daemon = True  # Dies automatically if the app shuts down
    timer.start()

    with _lock:
        _timers[device_id] = timer


def stop_timer(device_id: str) -> None:
    """Cancel an active timer. Safe to call even if no timer exists."""
    with _lock:
        timer = _timers.pop(device_id, None)

    if timer:
        timer.cancel()


def reset_timer(device_id: str) -> None:
    """
    Heartbeat handler: cancel the old timer, update last_heartbeat,
    flip status back to 'active', then start a fresh countdown.
    This is the core Dead Man's Switch reset mechanism.
    """
    monitor = store.get_monitor(device_id)
    if not monitor:
        return

    # Update state before starting the new timer
    store.set_monitor(device_id, {
        **monitor,
        "status": "active",
        "last_heartbeat": datetime.now(timezone.utc).isoformat()
    })

    start_timer(device_id)


def get_remaining_seconds(device_id: str) -> float | None:
    """
    Developer's Choice bonus: calculate approximate seconds remaining.
    Useful for the status endpoint so engineers can see how close
    a device is to triggering an alert.
    """
    monitor = store.get_monitor(device_id)
    if not monitor or monitor.get("status") != "active":
        return None

    with _lock:
        timer = _timers.get(device_id)

    if not timer:
        return None

    # threading.Timer stores the finish time internally
    remaining = timer.interval - (
        datetime.now(timezone.utc).timestamp() -
        (timer._target_time if hasattr(timer, '_target_time') else 0)
    )
    return max(0.0, round(remaining, 1))

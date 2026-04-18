"""
store.py — In-memory data store for monitors.

Uses a plain Python dictionary as the data layer.
Design decision: Separating storage from logic means swapping
this for Redis or SQLite only requires changing this one file.
"""

# Single source of truth for all monitors
# Key: device_id (str)  |  Value: monitor dict
_monitors: dict = {}


def get_monitor(device_id: str) -> dict | None:
    """Return monitor data or None if not found."""
    return _monitors.get(device_id)


def set_monitor(device_id: str, data: dict) -> None:
    """Create or overwrite a monitor entry."""
    _monitors[device_id] = data


def delete_monitor(device_id: str) -> None:
    """Remove a monitor permanently."""
    _monitors.pop(device_id, None)


def get_all_monitors() -> list[dict]:
    """Return all monitors as a list with their IDs embedded."""
    return [{"id": k, **v} for k, v in _monitors.items()]


def monitor_exists(device_id: str) -> bool:
    """Quick existence check."""
    return device_id in _monitors

"""
routes.py — All API endpoints for the Watchdog Sentinel.

Follows REST conventions:
  POST   /monitors              → Register a new monitor
  POST   /monitors/<id>/heartbeat → Reset countdown (keep alive)
  POST   /monitors/<id>/pause   → Pause monitoring (no alerts)
  GET    /monitors              → List all monitors (Developer's Choice)
  GET    /monitors/<id>         → Single monitor status (Developer's Choice)
  DELETE /monitors/<id>         → Deregister a monitor (Developer's Choice)
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

import store
import scheduler

bp = Blueprint("monitors", __name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# User Story 1: Register a Monitor
# ─────────────────────────────────────────────────────────────────────────────
@bp.route("/monitors", methods=["POST"])
def register_monitor():
    """
    Accept device registration and start its countdown timer.
    Returns 409 if the device ID already exists — prevents silent overwrites.
    """
    body = request.get_json()

    # Validate required fields
    required = ["id", "timeout", "alert_email"]
    missing = [f for f in required if not body or f not in body]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    device_id = body["id"]
    timeout = body["timeout"]
    alert_email = body["alert_email"]

    # Type validation
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        return jsonify({"error": "timeout must be a positive number (seconds)"}), 400

    # Conflict detection — don't silently overwrite a live monitor
    if store.monitor_exists(device_id):
        return jsonify({
            "error": f"Monitor '{device_id}' already exists. Send a heartbeat or delete it first."
        }), 409

    monitor = {
        "timeout": timeout,
        "alert_email": alert_email,
        "status": "active",
        "created_at": _now_iso(),
        "last_heartbeat": _now_iso()
    }

    store.set_monitor(device_id, monitor)
    scheduler.start_timer(device_id)

    return jsonify({
        "message": f"Monitor '{device_id}' registered. Countdown started: {timeout}s.",
        "monitor": {"id": device_id, **monitor}
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# User Story 2: Heartbeat — Reset the countdown
# ─────────────────────────────────────────────────────────────────────────────
@bp.route("/monitors/<device_id>/heartbeat", methods=["POST"])
def heartbeat(device_id):
    """
    Reset the countdown for a given device.
    Also automatically un-pauses a paused monitor.
    Returns 404 if the device ID is not registered.
    """
    if not store.monitor_exists(device_id):
        return jsonify({"error": f"Monitor '{device_id}' not found."}), 404

    monitor = store.get_monitor(device_id)
    was_paused = monitor.get("status") == "paused"

    scheduler.reset_timer(device_id)

    return jsonify({
        "message": f"Heartbeat received for '{device_id}'. Timer reset.",
        "status": "active",
        "was_paused": was_paused,
        "last_heartbeat": _now_iso()
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Bonus User Story: Pause monitoring
# ─────────────────────────────────────────────────────────────────────────────
@bp.route("/monitors/<device_id>/pause", methods=["POST"])
def pause_monitor(device_id):
    """
    Stop the countdown completely. No alerts will fire while paused.
    Calling heartbeat later automatically resumes monitoring.
    """
    if not store.monitor_exists(device_id):
        return jsonify({"error": f"Monitor '{device_id}' not found."}), 404

    monitor = store.get_monitor(device_id)

    if monitor.get("status") == "paused":
        return jsonify({"message": f"Monitor '{device_id}' is already paused."}), 200

    if monitor.get("status") == "down":
        return jsonify({
            "error": f"Monitor '{device_id}' has already triggered. Re-register it."
        }), 409

    scheduler.stop_timer(device_id)
    store.set_monitor(device_id, {**monitor, "status": "paused"})

    return jsonify({
        "message": f"Monitor '{device_id}' paused. No alerts will fire.",
        "status": "paused"
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Developer's Choice: GET endpoints — observability
# ─────────────────────────────────────────────────────────────────────────────
@bp.route("/monitors", methods=["GET"])
def list_monitors():
    """
    List all registered monitors and their current status.
    Rationale: A monitoring system with no way to query state forces
    engineers to grep logs — the exact problem CritMon is solving.
    """
    all_monitors = store.get_all_monitors()
    return jsonify({
        "count": len(all_monitors),
        "monitors": all_monitors
    }), 200


@bp.route("/monitors/<device_id>", methods=["GET"])
def get_monitor_status(device_id):
    """
    Return full status for one device, including time since last heartbeat.
    """
    if not store.monitor_exists(device_id):
        return jsonify({"error": f"Monitor '{device_id}' not found."}), 404

    monitor = store.get_monitor(device_id)

    # Calculate seconds since last heartbeat for added observability
    last_hb = monitor.get("last_heartbeat")
    seconds_since_heartbeat = None
    if last_hb:
        last_hb_dt = datetime.fromisoformat(last_hb)
        seconds_since_heartbeat = round(
            (datetime.now(timezone.utc) - last_hb_dt).total_seconds(), 1
        )

    return jsonify({
        "id": device_id,
        **monitor,
        "seconds_since_heartbeat": seconds_since_heartbeat
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Developer's Choice: DELETE — deregister a device
# ─────────────────────────────────────────────────────────────────────────────
@bp.route("/monitors/<device_id>", methods=["DELETE"])
def delete_monitor(device_id):
    """
    Cancel the timer and remove the monitor.
    Useful when a device is decommissioned — no need to restart the server.
    """
    if not store.monitor_exists(device_id):
        return jsonify({"error": f"Monitor '{device_id}' not found."}), 404

    scheduler.stop_timer(device_id)
    store.delete_monitor(device_id)

    return jsonify({
        "message": f"Monitor '{device_id}' deregistered and removed."
    }), 200

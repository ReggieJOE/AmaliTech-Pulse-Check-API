# AmaliTech Pulse-Check-API — "Watchdog" Sentinel

So basically this project is a backend API that keeps an eye on remote devices like solar farms and weather stations. The idea is simple — if a device goes quiet and stops sending signals, the system should notice and raise an alarm instead of waiting for a human to manually check logs.

I built this using **Python and Flask**.

---

## How It Works (Architecture)

Here's the flow I drew out before writing any code:

```
  User / Client
       |
       v
  [ MONITOR ]  --------->  [ Unknown ID? ]  -------->  [ 404 ]
       |
    if ACTIVE
       |
       v
signal=POST --> [ Timer running ] ---time=0--->  [ Status = "DOWN" ]
       |              ^                                    |
       |              |                                    v
       v              |                               [ ALERT ]
  [ Reset -> 20s ] ---+
                      |
                   if PAUSED
                      |
                 [ Stop Timer ]
```

**In plain English:**
- A device registers itself and a timer starts counting down
- If the device keeps sending signals (heartbeats), the timer resets — no problem
- If the signal stops and the timer hits zero, the status flips to **DOWN** and an alert fires
- If someone pauses the monitor (like during maintenance), the timer stops completely and no alerts go off
- If a device ID doesn't exist, the system just returns a **404**

---

## Project Structure

```
AmaliTech-Pulse-Check-API/
├── app.py          <- starts the Flask server, ties everything together
├── routes.py       <- all the API endpoints live here
├── scheduler.py    <- the timer logic, this is the core of everything
├── store.py        <- where monitor data is kept in memory
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Setup — How to Run It

### What you need
- Python 3.10+
- pip

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/ReggieJOE/AmaliTech-Pulse-Check-API.git
cd AmaliTech-Pulse-Check-API

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 4. Install Flask
pip install -r requirements.txt

# 5. Start the server
python app.py
```

You should see something like:
```
* Running on http://127.0.0.1:5000
* Debug mode: on
```

That means it's working.

---

## API Endpoints

### POST `/monitors` — Register a device

This is how a device introduces itself to the system. You send its ID, how long the timer should be, and who to alert if things go wrong.

```bash
curl -X POST http://localhost:5000/monitors \
  -H "Content-Type: application/json" \
  -d '{"id": "device-123", "timeout": 60, "alert_email": "admin@critmon.com"}'
```

**What you get back (201):**
```json
{
  "message": "Monitor 'device-123' registered. Countdown started: 60s.",
  "monitor": {
    "id": "device-123",
    "status": "active",
    "timeout": 60,
    "alert_email": "admin@critmon.com"
  }
}
```

If you try to register the same device twice, it returns **409** — it won't silently overwrite a live timer.

---

### POST `/monitors/{id}/heartbeat` — Send a signal (keep alive)

This is the device saying "hey I'm still here." Every time this is called, the timer resets back to the beginning.

```bash
curl -X POST http://localhost:5000/monitors/device-123/heartbeat
```

**What you get back (200):**
```json
{
  "message": "Heartbeat received for 'device-123'. Timer reset.",
  "status": "active"
}
```

If the device ID doesn't exist — **404**.

Also, if the monitor was paused, sending a heartbeat automatically wakes it back up. No need for a separate "un-pause" call.

---

### POST `/monitors/{id}/pause` — Pause the countdown

Say a technician is doing maintenance on a device. You don't want false alarms going off while they're working on it. This endpoint stops the timer completely.

```bash
curl -X POST http://localhost:5000/monitors/device-123/pause
```

**What you get back (200):**
```json
{
  "message": "Monitor 'device-123' paused. No alerts will fire.",
  "status": "paused"
}
```

When the device comes back online and sends a heartbeat, the monitor automatically resumes.

---

### GET `/monitors` — See all monitors

This just lists every device the system is currently tracking and what state they're in.

```bash
curl http://localhost:5000/monitors
```

**What you get back (200):**
```json
{
  "count": 2,
  "monitors": [
    { "id": "device-123", "status": "active", "timeout": 60 },
    { "id": "station-7", "status": "down", "timeout": 3600 }
  ]
}
```

---

### GET `/monitors/{id}` — Check one device

Same as above but for a single device. Also shows how many seconds have passed since the last heartbeat, which is pretty useful when you're debugging.

```bash
curl http://localhost:5000/monitors/device-123
```

**What you get back (200):**
```json
{
  "id": "device-123",
  "status": "active",
  "timeout": 60,
  "alert_email": "admin@critmon.com",
  "last_heartbeat": "2025-04-18T10:00:30+00:00",
  "seconds_since_heartbeat": 12.4
}
```

---

### DELETE `/monitors/{id}` — Remove a device

If a device gets decommissioned or you just want to clean up, this removes it from the system and cancels its timer.

```bash
curl -X DELETE http://localhost:5000/monitors/device-123
```

**What you get back (200):**
```json
{
  "message": "Monitor 'device-123' deregistered and removed."
}
```

---

### GET `/health` — Check if the server is alive

```bash
curl http://localhost:5000/health
```

```json
{ "status": "ok", "service": "Watchdog Sentinel" }
```

---

## What Happens When a Device Goes Silent

When a device's timer hits zero with no heartbeat received, this gets printed to the console:

```json
{
  "ALERT": "Device device-123 is down!",
  "alert_email": "admin@critmon.com",
  "time": "2025-04-18T10:01:00.000000+00:00"
}
```

And the device's status changes to `"down"` in the system.

In a real production setup, that `print()` in `scheduler.py` would be replaced with something like sending an email or hitting a webhook — but for this project, the console log does the job.

---

## Developer's Choice — Why I Added the GET and DELETE Endpoints

Honestly, I added these because I realized that while building the system, I had no way of actually seeing what was happening inside it. I could register a device and start a timer, but I couldn't tell if it was still active, when it last checked in, or whether the alert had already fired — not without digging through logs.

So I added `GET /monitors` and `GET /monitors/{id}` so you can just query the system directly and see everything at a glance. I also added `seconds_since_heartbeat` to the single monitor endpoint because knowing a device last checked in 55 seconds ago on a 60-second timer is way more useful than just knowing it's "active."

The `DELETE` endpoint came from a similar thought — what happens when a device gets physically removed or replaced? Without a way to deregister it, its dead entry just sits in the system forever. The delete endpoint solves that cleanly.

---

## A Few Design Choices I Made

- **`threading.Timer` for countdowns** — each device gets its own timer thread that fires exactly once when it expires. It's simple and maps directly to the problem.
- **Separate `store.py`** — I kept the data layer in its own file so if someone wanted to swap in a real database later, they'd only need to change that one file.
- **Heartbeat auto-unpauses** — I didn't want engineers to have to remember a separate "un-pause" call. If your device is back online and sending signals, that's enough — the system picks it back up automatically.
- **409 on duplicate registration** — silently overwriting a live timer felt dangerous. Better to say "this already exists, deal with it first."

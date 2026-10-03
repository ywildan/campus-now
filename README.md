# Campus Now

A lightweight, local-first real-time university schedule assistant for Linux.
Think "Now Playing" — but for classes.

No Docker. No cloud. No database. No internet required.

---

## What It Is

Campus Now answers the five questions you actually care about:

1. What class is happening right now?
2. What class is next?
3. How long until the next class starts?
4. When will the current class end?
5. What room is the class in?

It also shows today's full schedule, handles weekends (Friday–Sunday with no
classes), and wraps around from Sunday to Monday.

---

## Project Architecture

```
campus-now/
├── schedule.json          # Your schedule data (edit this each semester)
├── schedule.py            # Central scheduling engine (all logic lives here)
├── server.py              # Lightweight HTTP server + JSON API
├── notify.py              # Optional notification module (systemd timer)
├── web/
│   ├── index.html         # Web UI (Now Playing style)
│   ├── style.css          # Dark minimalist CSS
│   ├── app.js             # Vanilla JS (fetches API, updates in real-time)
│   ├── manifest.json      # PWA manifest
│   ├── icon-192.png       # PWA icon
│   └── icon-512.png       # PWA icon
├── scripts/
│   ├── campus-now         # Python CLI (now, next, today, tomorrow, week, panel, json)
│   ├── next-class.sh      # Bash wrapper for Noctalia panel output
│   ├── campus-now-notify.service    # systemd service for notifications
│   └── campus-now-notify.timer      # systemd timer (5-min check)
├── tests/
│   └── test_schedule.py   # 25 unit/integration tests for the engine
├── requirements.txt       # No external deps (stdlib only)
└── README.md
```

**Key design decisions:**

- `schedule.py` is the **single source of truth** for all scheduling logic.
  The CLI, web server, and notification module all import from it — no logic
  is duplicated.
- The web frontend fetches from `/api/status`, `/api/today`, `/api/week` —
  it never calculates anything itself.
- The HTTP server uses only Python's built-in `http.server` — zero dependencies.
- Timezone is handled with `zoneinfo` (Python 3.9+) using `Asia/Jakarta`.

---

## Installation

```bash
cd ~/Projects
git clone https://github.com/ywildan/campus-now.git
cd campus-now
chmod +x scripts/campus-now scripts/next-class.sh
```

No pip install needed — the engine uses only the Python standard library.

**Requirements:**
- Python 3.9+ (for native `zoneinfo` support)
- For notifications: `libnotify` (provides `notify-send`)

---

## Running Locally

### CLI

```bash
# From the project directory:
./scripts/campus-now now      # current + next class
./scripts/campus-now next     # next upcoming class
./scripts/campus-now today    # all classes today
./scripts/campus-now tomorrow # tomorrow's classes
./scripts/campus-now week     # full week overview
./scripts/campus-now json     # full JSON status dump
./scripts/campus-now panel    # JSON for Noctalia widget
```

### Web Interface

```bash
python3 server.py 8888
```

Then open: http://localhost:8888

The page auto-refreshes every 60 seconds.

### Using the built-in HTTP server (alternative)

```bash
# Serve the web directory with Python's built-in server:
cd web
python3 -m http.server 8888
# Then the frontend must be served from the same origin as the API.
# For a combined server, use: python3 server.py 8888
```

---

## CLI Commands

| Command | Description |
|---|---|
| `campus-now now` | Show current class (with countdown & progress) + next class |
| `campus-now next` | Show next upcoming class (today or future day) |
| `campus-now today` | List all classes today |
| `campus-now tomorrow` | List all classes tomorrow |
| `campus-now week` | List all classes for the week |
| `campus-now panel` | Output JSON for Noctalia/Hyprland panel widget |
| `campus-now json` | Full JSON status dump (useful for scripting) |

---

## Web Interface

The web UI is a dark, minimalist "Now Playing" card:

- **Main card**: shows either the current class (with a progress bar and
  "Ends in X min") or the next class (with "Starts in Xh Ym").
- **Today's schedule**: a scrollable list of today's classes with
  subject, time, and room.

The page refreshes automatically every 60 seconds via JavaScript polling
of `/api/status` and `/api/today`.

### PWA (Progressive Web App)

The web UI includes a `manifest.json` and app icons, so it can be
"installed" on your phone:

1. Open `http://<your-computer-ip>:8888` on your phone (same network).
2. Tap the browser's "Add to Home Screen" option.
3. Tap the icon — it opens in standalone mode, no browser chrome.

---

## Editing schedule.json

Schedule data lives entirely in `schedule.json`. Edit it whenever your
semester changes.

```json
{
  "timezone": "Asia/Jakarta",
  "days": {
    "monday": [
      {
        "subject": "Pengantar Bisnis",
        "code": "002046",
        "sks": 3,
        "lecturer": "Masculine Muhammad Muqorobin, S.E., M.Si.",
        "class": "01",
        "start": "15:10",
        "end": "17:40",
        "room": "A.3b.4"
      }
    ],
    "tuesday": [ ... ],
    ...
  }
}
```

**Fields:**

| Field | Required | Description |
|---|---|---|
| `subject` | Yes | Course name |
| `code` | No | Course code |
| `sks` | No | Credit hours |
| `lecturer` | No | Instructor name |
| `class` | No | Class/sections number |
| `start` | Yes | `HH:MM` 24-hour format |
| `end` | Yes | `HH:MM` 24-hour format |
| `room` | No | Room/building |

**Validation** — the engine validates the file on load and gives clear errors
for:
- Invalid day name (must be `monday`–`sunday`)
- Invalid time format (must be `HH:MM`)
- Out-of-range time (e.g. `25:00`)
- End time earlier than start time
- Missing `subject`, `start`, or `end`

To validate your schedule:

```bash
python3 schedule.py json
```

---

## Noctalia / Hyprland Integration

The project includes a panel-output mode that produces JSON suitable for
Noctalia module consumption.

### 1. Test the integration script

```bash
cd ~/Projects/campus-now
./scripts/next-class.sh
```

Expected output (example):

```json
{
  "text": "󰃭 Bahasa · 10:00 · 1h 24m",
  "tooltip": "Bahasa Inggris\nTuesday 10:00 - 11:40\nA.4b.7 (Lab. Komputer)\nStarts in 1h 24m",
  "state": "next"
}
```

### 2. Noctalia module configuration

Inspect your existing Noctalia configuration first:

```bash
# Find your Noctalia config
find ~/.config/noctalia -name "*.json" -o -name "*.yaml" -o -name "*.yml" 2>/dev/null
```

Then add a custom module entry. Example Noctalia config snippet:

```json
{
  "module": {
    "type": "custom",
    "name": "campus-now",
    "interval": 60,
    "command": "/home/ywldan/Projects/campus-now/scripts/next-class.sh",
    "parser": "json"
  }
}
```

**Fields explained:**
- `interval: 60` — refresh every 60 seconds
- `command` — runs the script and reads stdout as JSON
- `parser: "json"` — Noctalia parses the JSON for `text`, `tooltip`, and `state`

### 3. Panel output states

| State | Text format | When |
|---|---|---|
| `now` | `󰑮 Subject · 47m left` | Class is in progress |
| `next` | `󰃭 Subject · 10:00 · 1h 24m` | Class upcoming |
| `none` | `󰃭 No class` | No classes for 7 days |

### 4. Optional: keyboard shortcut in Hyprland

Add to your `~/.config/hypr/hyprland.conf` (after inspecting it):

```
bind = $mod, C, exec, python3 /home/ywldan/Projects/campus-now/scripts/campus-now now
```

This will print the current class info to a terminal or notification.

---

## Desktop Integration

The repository ships a working Noctalia v5 bar widget and a systemd user
service. Live files are kept under `integrations/`:

```
integrations/
├── noctalia/
│   ├── plugin.toml         # plugin manifest (id = noctalia/campus-now)
│   └── widget.luau         # bar widget: reads next-class.sh, tooltip, click -> dashboard
└── systemd/
    └── campus-now.service  # user service for the web dashboard on :8888
```

Install everything with:

```bash
./scripts/install-desktop-integration.sh
```

That script copies the plugin into `~/.local/share/noctalia/plugins/campus-now/`,
installs + starts the systemd user service, then prints the remaining manual
steps (enable plugin + add widget to bar). It never overwrites Noctalia's
`settings.toml`.

### Noctalia v5

Install the local plugin at:

```
~/.local/share/noctalia/plugins/campus-now/
```

That is the directory directly under `.../plugins/` — a common mistake is the
nested author-folder form. Do **NOT** place it at:

```
~/.local/share/noctalia/plugins/noctalia/campus-now/   # wrong
```

Noctalia v5 scans `~/.local/share/noctalia/plugins/<plugin>/` directly as a
built-in *local* source. Sub-folders mirroring the git-repo author/plugin
layout are only used for git sources, not for local plugins.

**Working plugin ID:** `noctalia/campus-now`

**Enable the plugin:**

```bash
cp -r integrations/noctalia ~/.local/share/noctalia/plugins/campus-now
noctalia msg plugins enable noctalia/campus-now
noctalia config validate
```

`config validate` should print `✓ Config is valid` with no
"unrecognized widget type" warning.

**Add the widget to the bar:** this cannot be automated safely because it
depends on your bar layout. In Noctalia **Settings → Bar**, use **Add widget**
and pick **Campus Now** (`next-class`). Or, if you configure the bar by hand,
add it to the center list and declare the widget:

```toml
[bar.default]
center = [ "clock", "campus-now" ]

[widget.campus-now]
type = "noctalia/campus-now:next-class"
```

**Portability notes:** `widget.luau` already resolves its path home-relatively
(`noctalia.expandPath("~/Projects/campus-now/scripts/next-class.sh")`), so it
works from any home directory as long as the project sits at
`~/Projects/campus-now`. If your project lives elsewhere, edit that one path.

### systemd user service

Install manually:

```bash
mkdir -p ~/.config/systemd/user
cp integrations/systemd/campus-now.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now campus-now.service
```

The service uses `%h/Projects/campus-now` as its base, so it is home-relative
and works on any machine where the project lives at `~/Projects/campus-now`.

**Verify:**

```bash
systemctl --user status campus-now.service
curl -s http://localhost:8888/api/status
```

**Stop / disable:**

```bash
systemctl --user disable --now campus-now.service
```

If your project is not at `~/Projects/campus-now`, edit
`integrations/systemd/campus-now.service` and replace `%h/Projects/campus-now`.

---

## Optional Notifications

Campus Now can send desktop notifications 30 minutes and 10 minutes before
class starts. It uses a **systemd user timer** (no busy-loop process).

### Setup

```bash
# Copy the service and timer files
mkdir -p ~/.config/systemd/user
cp ~/Projects/campus-now/scripts/campus-now-notify.service ~/.config/systemd/user/
cp ~/Projects/campus-now/scripts/campus-now-notify.timer ~/.config/systemd/user/

# Fix the path in the service file if your project is elsewhere:
# Edit ~/.config/systemd/user/campus-now-notify.service
# Change ExecStart path to match your project location.

# Enable and start the timer
systemctl --user daemon-reload
systemctl --user enable campus-now-notify.timer
systemctl --user start campus-now-notify.timer
```

### How it works

- The timer fires every 5 minutes.
- Each run checks if any class starts in exactly 30 or 10 minutes.
- Notifications are deduplicated using a state file at
  `~/.cache/campus-now/notification-state.json`.
- After the class starts, the state is cleared for that class.

### Test notifications manually

```bash
python3 ~/Projects/campus-now/notify.py
```

---

## API

All endpoints return JSON.

### GET /api/status

Full status snapshot:

```json
{
  "state": "now",
  "datetime": "2026-09-14T16:00:00+07:00",
  "current": {
    "subject": "Pengantar Akuntansi",
    "code": "002047",
    "sks": 3,
    "lecturer": "Retnosari, S.Pd., M.Si.",
    "start": "12:30",
    "end": "15:00",
    "room": "A.3b.6",
    "minutes_remaining": 120,
    "progress": 0.68
  },
  "next": {
    "subject": "Matematika Bisnis",
    "day": "thursday",
    "day_name": "Thursday",
    "start": "07:00",
    "end": "09:30",
    "room": "A.3b.2",
    "minutes_until": 880
  },
  "today": [ ... ],
  "classes_finished": false
}
```

### GET /api/today

```json
{
  "day": "Wednesday",
  "classes": [
    {
      "subject": "Ketentuan Umum Perpajakan",
      "start": "07:00",
      "end": "08:40",
      "room": "A.3b.5",
      "is_current": false
    }
  ],
  "current": null,
  "next_today": { ... },
  "classes_finished": false
}
```

### GET /api/week

```json
{
  "week": {
    "Monday": [ ... ],
    "Tuesday": [ ... ],
    ...
  }
}
```

### GET /api/next

Convenience endpoint returning just the next class.

---

## Troubleshooting

### "No module named 'schedule'"

Make sure you're running the CLI from the project directory, or that the
script can find `schedule.py`. The `campus-now` script adds the project
root to `sys.path` automatically.

### Time is wrong

The engine reads the timezone from `schedule.json` (default: `Asia/Jakarta`).
Make sure your system clock is set correctly:

```bash
date
timedatectl status
```

### Web page shows no data

Make sure the server is running:

```bash
python3 server.py 8888
```

Then open `http://localhost:8888` and check browser dev tools for errors.

### Notifications not showing

1. Verify `notify-send` works:
   ```bash
   notify-send "Test" "Campus Now"
   ```
2. Check if the timer is active:
   ```bash
   systemctl --user list-timers campus-now-notify
   ```
3. Check notification state:
   ```bash
   cat ~/.cache/campus-now/notification-state.json
   ```
4. Run manually for debugging:
   ```bash
   python3 ~/Projects/campus-now/notify.py
   ```

### Classes don't appear

Validate your schedule:

```bash
python3 schedule.py json
# If there's a validation error, it will print to stderr.
```

Make sure day names are lowercase (`monday`, `tuesday`, etc.) and times are
in `HH:MM` 24-hour format.

### Port 8080 already in use

Use a different port:

```bash
python3 server.py 9090
```

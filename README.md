# ScheduleBot 🗓️

A Discord bot for game-development teams that generates a **24-hour × 7-day availability heat-map** natively inside Discord using slash commands.

---

## Features

| Feature | Detail |
|---|---|
| `/schedule start <title>` | Creates a weekly grid embed with dropdown UI attached |
| `/schedule view` | Privately sends the user the heat-map in their timezone |
| `/set_timezone <tz>` | Saves a user's IANA timezone for personalised views |
| **Day dropdown** | Multi-select Monday → Sunday |
| **Hour dropdown** | Multi-select 00:00 → 23:00 (24-hour format) |
| **Submit button** | Saves availability & regenerates the PNG in real-time |
| **Heat-map colours** | Light grey (0) → light green (low) → dark green (max overlap) |
| **Persistent UI** | Dropdowns & buttons still work after a bot restart |
| **SQLite storage** | Zero-dependency database; easy to migrate to Postgres later |

---

## Project Structure

```
schedulebot/
├── bot.py               # Entry point — intents, lifecycle, cog loading
├── requirements.txt     # Python dependencies
├── .env.example         # Template for environment variables
├── .gitignore
├── cogs/
│   └── schedule.py      # Slash commands: /schedule start|view, /set_timezone
└── utils/
    ├── database.py      # Async SQLite data-access layer (aiosqlite)
    ├── heatmap.py       # Pillow-based PNG grid generator
    └── ui.py            # Persistent Discord UI (dropdowns + button)
```

---

## Prerequisites

- Python 3.11 or newer
- A Discord application & bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- The bot must have the **`applications.commands`** and **`bot`** scopes plus the **Send Messages** and **Attach Files** permissions.

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/dotnetdork/schedulebot.git
cd schedulebot

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set DISCORD_TOKEN to your bot token

# 5. Run the bot
python bot.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Your Discord bot token |
| `DATABASE_PATH` | ❌ | `data/schedulebot.db` | Path to the SQLite file |
| `DEFAULT_TIMEZONE` | ❌ | `UTC` | Fallback timezone for new users |

---

## Usage

### Create a schedule
```
/schedule start Sprint 42 Planning
```
Posts an embed with an empty heat-map and interactive dropdowns in the current channel.

### Submit availability
1. Choose **day(s)** in the first dropdown (multi-select, Monday–Sunday).
2. Choose **hour(s)** in the second dropdown (multi-select, 00:00–23:00).
3. Press **✅ Submit / Update My Availability**.

The heat-map image updates immediately to reflect the new overlap.

### View in your timezone
```
/set_timezone America/New_York
/schedule view
```
Sends an ephemeral (private) message with the heat-map shifted to your local time.

---

## Heat-Map Colour Scale

| Colour | Meaning |
|---|---|
| Light grey | No one available |
| Light green | At least one person available |
| Dark green | Maximum team overlap |

The shade is a linear interpolation between light and dark green, relative to the cell with the highest respondent count.

---

## Architecture & Future Expansion

The codebase is structured for easy expansion:

- **`utils/database.py`** — all data access goes through the `Database` class. To add Google Calendar OAuth tokens, add a new table and methods here.
- **`cogs/schedule.py`** — add new slash commands by adding methods to `ScheduleCog`.
- **`utils/heatmap.py`** — pure image-rendering logic with no Discord dependency; can be used standalone or in tests.
- **`utils/ui.py`** — persistent Discord UI components; extend with new dropdowns or buttons as needed.

### Planned Google Calendar Integration
1. Add a `google_calendar_tokens` table in `database.py`.
2. Add a `/calendar connect` command in a new `cogs/calendar.py` cog.
3. Import events from the Calendar API and pre-populate the availability grid.

---

## License

MIT

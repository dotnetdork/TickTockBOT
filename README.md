# ScheduleBot

ScheduleBot is a Discord bot that creates a weekly availability heatmap in a channel and lets teammates submit availability through interactive dropdowns.

## What Commands Exist?

There are two command types in this project:

1. Terminal commands you run locally (setup/run).
2. Discord slash commands users run in a server.

Both are documented below.

## Prerequisites

- Python 3.11+
- A Discord application and bot token
- Bot invite scopes: `bot` and `applications.commands`
- Bot permissions at minimum: Send Messages, Attach Files, Use Slash Commands

## Terminal Commands (Local Setup)

### 1) Clone and enter the project

```bash
git clone https://github.com/dotnetdork/schedulebot.git
cd schedulebot
```

### 2) Create a virtual environment

```bash
python -m venv venv
```

### 3) Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
venv\Scripts\activate.bat
```

Git Bash (or other bash-like shell on Windows):

```bash
source venv/Scripts/activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

### 4) Install dependencies

```bash
pip install -r requirements.txt
```

### 5) Create environment file

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux/Git Bash:

```bash
cp .env.example .env
```

Then edit `.env` and set `DISCORD_TOKEN`.

### 6) Run the bot

```bash
python bot.py
```

## Discord Slash Commands (In Server)

### `/schedule start <title>`

Creates a new schedule post in the current channel.

Example:

```text
/schedule start Sprint Planning
```

Result:

- Bot posts an embed with an empty weekly heatmap.
- Post includes interactive day/hour dropdowns and a submit button.

### `/schedule view`

Shows the latest schedule in the current channel as a private (ephemeral) response, shifted into your saved timezone.

Example:

```text
/schedule view
```

### `/set_timezone <timezone>`

Saves your preferred IANA timezone.

Example:

```text
/set_timezone America/New_York
```

Common values:

- `UTC`
- `America/New_York`
- `Europe/London`
- `Asia/Tokyo`

## Interactive UI Actions

After running `/schedule start`:

1. Select one or more days.
2. Select one or more hours (`00:00` to `23:00`).
3. Click `Submit / Update My Availability`.

The bot stores your availability and regenerates the heatmap image.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | Yes | none | Discord bot token |
| `DATABASE_PATH` | No | `data/schedulebot.db` | SQLite database file path |
| `DEFAULT_TIMEZONE` | No | `UTC` | Default timezone for users without a saved timezone |

## Troubleshooting Commands

### `ModuleNotFoundError: No module named 'discord'`

Install dependencies in the active venv:

```bash
pip install -r requirements.txt
```

### `source: The term 'source' is not recognized` (PowerShell)

Use PowerShell activation command:

```powershell
.\venv\Scripts\Activate.ps1
```

### Slash commands not appearing yet

What to do:

1. Ensure the bot was invited with `applications.commands` scope.
2. Restart the bot.
3. Wait a few minutes for global command propagation.

## Project Structure

```text
schedulebot/
    bot.py
    requirements.txt
    cogs/
        schedule.py
    utils/
        database.py
        heatmap.py
        ui.py
```

## License

MIT

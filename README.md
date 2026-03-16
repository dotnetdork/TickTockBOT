# TickTock Bot 🎯

**TickTock** is a modern, production-ready Discord bot that helps teams coordinate availability through interactive schedules and live-updating heatmaps. Built for game dev teams and any group that needs to sync schedules efficiently.

[![Discord.py](https://img.shields.io/badge/discord.py-2.3.2%2B-blue.svg)](https://github.com/Rapptz/discord.py)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## ✨ Features

- 🗓️ **Interactive Weekly Schedules** - Team members select availability via intuitive dropdowns
- 🎨 **Live-Updating Heatmaps** - Visual representation shows when most people are available
- 🌍 **Timezone Support** - Store times in UTC, view in your local timezone
- ♿ **Dyslexia-Friendly Design** - High contrast colors, thick borders, clean padding, 12-hour AM/PM format
- 🔄 **Update Anytime** - Change your availability as many times as needed
- 💾 **Persistent UI** - Buttons and dropdowns work even after bot restarts
- 🎯 **Live Monitor Feel** - No blank images - the heatmap appears only after submissions

## 📸 What It Looks Like

When you run `/schedule start`, TickTock posts an embed with interactive dropdowns:

```
📅 Sprint Planning

Welcome to TickTock! 🎯

Use the dropdowns below to select your available days and hours,
then press Submit to save your availability.

💡 The heatmap will appear here after the first person submits!

[Day Selector Dropdown]
[Hour Selector Dropdown]
[✅ Submit / Update My Availability Button]
```

After team members submit, a color-coded heatmap appears showing availability overlap:
- **Light grey**: No one available
- **Light green**: Few people available
- **Dark saturated green**: Many people available

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- A Discord bot token ([Create one here](https://discord.com/developers/applications))
- Bot permissions: `View Channels`, `Send Messages`, `Attach Files`, `Embed Links`, `Use Slash Commands`

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/dotnetdork/schedulebot.git
   cd schedulebot
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   - **Windows PowerShell:**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```

   - **Windows CMD:**
     ```cmd
     venv\Scripts\activate.bat
     ```

   - **Git Bash (Windows):**
     ```bash
     source venv/Scripts/activate
     ```

   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**

   - **Windows PowerShell:**
     ```powershell
     Copy-Item .env.example .env
     ```

   - **macOS/Linux/Git Bash:**
     ```bash
     cp .env.example .env
     ```

   Then edit `.env` and add your bot token:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   DATABASE_PATH=data/schedulebot.db
   DEFAULT_TIMEZONE=UTC
   ```

6. **Run the bot**
   ```bash
   python bot.py
   ```

You should see:
```
[INFO] ticktock: Extensions loaded. Slash command tree has X top-level commands.
[INFO] ticktock: Logged in as TickTock#1234 (ID: ...)
[INFO] ticktock: Synced X application command(s) globally.
[INFO] ticktock: TickTock Bot is ready.
```

## 📋 Commands

### `/schedule start <title>`

Creates a new availability schedule in the current channel.

**Example:**
```
/schedule start Sprint 42 Planning
```

**What happens:**
1. Bot posts an embed with interactive day/hour dropdowns
2. Team members select their availability and click Submit
3. Heatmap appears and updates live as people respond

---

### `/schedule view`

View the latest schedule in the current channel, converted to your personal timezone. This is sent as an ephemeral message (only you can see it).

**Example:**
```
/schedule view
```

**Note:** Set your timezone first with `/set_timezone` to see times in your local timezone.

---

### `/set_timezone <timezone>`

Save your preferred IANA timezone for personalized schedule views.

**Example:**
```
/set_timezone America/New_York
```

**Common timezones:**
- `UTC`
- `America/New_York` (US Eastern)
- `America/Los_Angeles` (US Pacific)
- `America/Chicago` (US Central)
- `Europe/London` (UK)
- `Europe/Paris` (Central European)
- `Asia/Tokyo` (Japan)
- `Australia/Sydney` (Australia)

See the [full list of IANA timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---

### `/help`

Display a helpful guide about TickTock's features and workflow.

**Example:**
```
/help
```

---

### `/permissions`

Get the OAuth2 invite link with the exact permissions TickTock needs. Share this with server admins for easy setup.

**Example:**
```
/permissions
```

**Required permissions (Permission Integer: `52224`):**
- ✅ **View Channels** - Read channel information
- ✅ **Send Messages** - Post schedules and responses
- ✅ **Attach Files** - Upload heatmap images
- ✅ **Embed Links** - Display rich embeds
- ✅ **Use Slash Commands** - Enable `/schedule` and other commands

## 🌐 Inviting TickTock to Your Server

Use this link to invite TickTock with the correct permissions:

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=52224&scope=bot%20applications.commands
```

Replace `YOUR_BOT_CLIENT_ID` with your bot's client ID from the [Discord Developer Portal](https://discord.com/developers/applications).

**Or use the `/permissions` command** once the bot is running to get a ready-to-share invite link!

## 🛠️ Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | ✅ Yes | - | Your Discord bot token |
| `DATABASE_PATH` | ❌ No | `data/schedulebot.db` | Path to SQLite database file |
| `DEFAULT_TIMEZONE` | ❌ No | `UTC` | Default timezone for users without a saved preference |

## 📦 Deployment

### Deploy to JustRunMy.app

[JustRunMy.app](https://justrunmy.app) is a simple hosting platform for Discord bots. Here's how to deploy TickTock:

#### Step 1: Prepare Your Files

1. **DO NOT zip the parent folder** - Select the files directly to zip
2. **Exclude the `.git` folder** - This reduces file size and prevents conflicts
3. **Include these files in your zip:**
   - `bot.py`
   - `requirements.txt`
   - `.env.example` (optional, for reference)
   - `cogs/` folder
   - `utils/` folder
   - `discloud.config` (optional, for Discloud hosting)

**Creating the zip:**

- **Windows:** Select all required files → Right-click → "Send to" → "Compressed (zipped) folder"
- **macOS:** Select all required files → Right-click → "Compress X items"
- **Linux:**
  ```bash
  zip -r schedulebot.zip bot.py requirements.txt cogs/ utils/ discloud.config
  ```

#### Step 2: Upload to JustRunMy.app

1. Go to [JustRunMy.app](https://justrunmy.app)
2. Create an account or log in
3. Click **"New Application"**
4. Upload your `schedulebot.zip` file
5. Set the **Entry Point** to: `bot.py`

#### Step 3: Configure Environment Variables

In the JustRunMy.app dashboard, add these environment variables:

| Key | Value |
|-----|-------|
| `DISCORD_TOKEN` | Your Discord bot token |
| `DATABASE_PATH` | `data/schedulebot.db` (or leave default) |
| `DEFAULT_TIMEZONE` | `UTC` (or your preferred default) |

**Important:** Never commit your `.env` file with your token to Git. Always add environment variables through your hosting platform's dashboard.

#### Step 4: Start the Bot

1. Click **"Deploy"** or **"Start"**
2. Monitor the logs to ensure the bot starts successfully
3. Look for: `TickTock Bot is ready.`

#### Step 5: Verify in Discord

1. Go to a Discord server where the bot is invited
2. Type `/help` to verify commands are registered
3. Create a test schedule with `/schedule start Test`

### Deploy to Other Platforms

TickTock works on any Python hosting platform:

- **Heroku**: Use the provided `requirements.txt` and set environment variables in the dashboard
- **Railway.app**: Connect your GitHub repo and set environment variables
- **DigitalOcean App Platform**: Deploy from GitHub with automatic builds
- **Self-hosted**: Run `python bot.py` in a screen/tmux session or systemd service

### Requirements

All platforms need:
- Python 3.11+
- The packages in `requirements.txt`:
  - `discord.py>=2.3.2`
  - `aiosqlite>=0.19.0`
  - `Pillow>=10.0.0`
  - `pytz>=2024.1`
  - `python-dotenv>=1.0.0`

## 🏗️ Project Structure

```
schedulebot/
├── bot.py                  # Entry point, bot lifecycle management
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── discloud.config         # Discloud deployment config
├── README.md               # This file
│
├── cogs/
│   ├── __init__.py
│   └── schedule.py         # Slash commands (/schedule, /set_timezone, /help, /permissions)
│
└── utils/
    ├── __init__.py
    ├── database.py         # Async SQLite wrapper (schedules, availability, user_timezones)
    ├── heatmap.py          # PNG heatmap generation with Pillow
    └── ui.py               # Discord UI components (dropdowns, buttons, persistent views)
```

## 🎨 Design Philosophy

### Dyslexia-Friendly Features

TickTock was designed with accessibility in mind:

- **12-hour AM/PM format** instead of 24-hour military time
- **High contrast colors** (pure white background, dark text, saturated greens)
- **Thick cell borders** (2px) for clear visual separation
- **Clean padding** for reduced visual clutter
- **Sans-serif fonts** with fallbacks (DejaVuSans, Liberation Sans, Arial)
- **Larger cells** for improved readability

### Live Monitor Experience

Unlike static bots that post a blank grey image immediately:

1. `/schedule start` posts **only the embed and UI** (no image)
2. First user submits → **Heatmap appears**
3. Each submission → **Heatmap updates live**

This creates a responsive, dashboard-like feel instead of a static form.

## 🔧 Troubleshooting

### Slash commands not appearing

**Solution:**
1. Ensure the bot was invited with the `applications.commands` scope
2. Restart the bot
3. Wait 1-5 minutes for global command propagation
4. Try running `/help` in a channel where the bot has permissions

---

### `ModuleNotFoundError: No module named 'discord'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

---

### `source: The term 'source' is not recognized` (PowerShell)

**Solution:**
Use the PowerShell activation command:
```powershell
.\venv\Scripts\Activate.ps1
```

---

### `❌ Missing Permissions - I don't have permission to attach files`

**Solution:**
1. Go to Server Settings → Roles → TickTock Bot
2. Enable **Attach Files** permission
3. Or go to Channel Settings → Permissions → TickTock Bot
4. Enable **Attach Files** for that specific channel

---

### Database locked errors

**Solution:**
- SQLite databases can be locked if multiple processes access them
- Ensure only one instance of the bot is running
- Restart the bot if needed

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

**Code style:**
- Follow PEP 8 conventions
- Use type hints where applicable
- Add docstrings for new functions/classes
- Keep functions focused and modular

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **discord.py** - Excellent Discord API wrapper
- **Pillow** - Powerful Python image library
- **pytz** - Timezone handling made easy
- **aiosqlite** - Async SQLite support

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/dotnetdork/schedulebot/issues)
- **Discussions:** [GitHub Discussions](https://github.com/dotnetdork/schedulebot/discussions)
- **Discord:** Use the `/help` command in your server

---

Made with ❤️ for game dev teams and busy groups everywhere.

**TickTock** - Because coordinating schedules shouldn't be chaos.

"""
bot.py
------
Entry point for ScheduleBot.

Startup sequence
----------------
1. Load environment variables from .env (token, DB path, default TZ).
2. Initialise the SQLite database.
3. Create the Discord bot with the required intents.
4. Load the Schedule cog which registers all slash commands.
5. On ``on_ready``, sync the application-command tree to Discord and
   re-register all persistent views so button/dropdown interactions
   continue to work after a restart.

Running the bot
---------------
    python bot.py

Or with explicit .env file path:
    DOTENV_PATH=/path/to/.env python bot.py

Environment variables (see .env.example)
-----------------------------------------
DISCORD_TOKEN    – required – your bot token
DATABASE_PATH    – optional – defaults to data/schedulebot.db
DEFAULT_TIMEZONE – optional – defaults to UTC
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database
from utils.ui import ScheduleView

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("schedulebot")


# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

load_dotenv()

TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DB_PATH: str = os.getenv("DATABASE_PATH", "data/schedulebot.db")

if not TOKEN:
    logger.critical(
        "DISCORD_TOKEN is not set.  "
        "Copy .env.example to .env and fill in your bot token."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Bot class
# ---------------------------------------------------------------------------

class ScheduleBot(commands.Bot):
    """
    Custom Bot subclass that owns the database connection and handles the
    full startup / teardown lifecycle.

    Attaching the database to the bot object (``self.db``) rather than using
    a module-level global makes it straightforward to inject into cogs and
    makes unit-testing easier.
    """

    def __init__(self) -> None:
        # Minimal intents: we only need to read guilds and message content
        # is NOT needed for slash commands.
        intents = discord.Intents.default()
        # guild_messages is used so the bot can read message content in guilds
        # if needed for future prefix-command support.
        intents.guild_messages = True

        super().__init__(
            command_prefix="!",   # fallback prefix (unused – slash commands only)
            intents=intents,
            # Sync the command tree automatically only in development.
            # In production, call tree.sync() once from on_ready.
        )

        self.db: Database = Database(DB_PATH)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def setup_hook(self) -> None:
        """
        Called once before the bot connects to Discord.
        This is the right place to:
        - Open the DB connection.
        - Load cogs (which registers slash commands with the tree).
        """
        await self.db.connect()

        # Load the schedule cog.  The cog's setup() function will attach
        # command groups to bot.tree.
        await self.load_extension("cogs.schedule")

        logger.info("Extensions loaded.  Slash command tree has %d top-level commands.",
                    len(self.tree.get_commands()))

    async def on_ready(self) -> None:
        """
        Called when the bot has connected to Discord and is ready to receive
        events.  We sync the command tree and re-register persistent views.
        """
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]

        # Sync slash commands to Discord.
        # In production you might want to scope this to a single guild to
        # avoid the 1-hour propagation delay for global commands.
        synced = await self.tree.sync()
        logger.info("Synced %d application command(s) globally.", len(synced))

        # Re-register all active persistent views so interactions fired
        # against old messages continue to work.
        await self._register_persistent_views()

        logger.info("ScheduleBot is ready.")

    async def close(self) -> None:
        """Gracefully close the DB connection when the bot shuts down."""
        await self.db.close()
        await super().close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _register_persistent_views(self) -> None:
        """
        Re-create and register a ``ScheduleView`` for every active schedule
        in the database so that component interactions still work after a
        bot restart.

        discord.py requires that persistent views be added via
        ``bot.add_view()`` before any interaction for that view is received.
        The view does not need to be attached to a specific message at this
        point; discord.py matches interactions to views by custom_id prefix.
        """
        # Fetch every schedule that has a message_id (i.e. has been posted)
        try:
            async with self.db.conn.execute(
                "SELECT id FROM schedules WHERE message_id IS NOT NULL"
            ) as cursor:
                rows = await cursor.fetchall()

            count = 0
            for row in rows:
                view = ScheduleView(schedule_id=row["id"], db=self.db)
                self.add_view(view)
                count += 1

            logger.info("Re-registered %d persistent view(s).", count)
        except Exception as exc:
            logger.exception("Failed to re-register persistent views: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Instantiate and run the bot."""
    bot = ScheduleBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

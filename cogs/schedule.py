"""
cogs/schedule.py
----------------
The main cog for ScheduleBot.

Slash Commands
--------------
/schedule start <title>
    Create a new weekly availability grid in the current channel.
    Posts an embed with the heatmap image and persistent UI controls.

/schedule view
    Privately sends the user the current schedule heatmap, adjusted to
    their saved timezone (defaults to UTC if unset).

/set_timezone <timezone>
    Save the user's preferred IANA timezone so that /schedule view
    and future grids render in their local time.

Architecture note
-----------------
The cog receives a ``Database`` instance via its constructor — a standard
dependency-injection pattern that keeps the cog testable and makes it easy
to swap storage backends later (e.g. when adding Google Calendar support).
"""

from __future__ import annotations

import io
import logging

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from utils.database import Database
from utils.heatmap import generate_heatmap
from utils.ui import ScheduleView, build_schedule_embed

logger = logging.getLogger(__name__)


class ScheduleCog(commands.Cog, name="Schedule"):
    """Cog that owns all schedule-related slash commands."""

    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    # ------------------------------------------------------------------
    # /schedule  (top-level group)
    # ------------------------------------------------------------------

    schedule_group = app_commands.Group(
        name="schedule",
        description="Create and view weekly availability schedules.",
    )

    # ------------------------------------------------------------------
    # /schedule start <title>
    # ------------------------------------------------------------------

    @schedule_group.command(
        name="start",
        description="Create a new weekly availability grid in this channel.",
    )
    @app_commands.describe(title="A short name for this schedule, e.g. 'Sprint 42 Planning'")
    async def schedule_start(
        self,
        interaction: discord.Interaction,
        title: str,
    ) -> None:
        """
        1. Defer the interaction immediately.
        2. Create a database row for the schedule.
        3. Post the embed + persistent view (NO image yet - live monitor feel).
        4. Store the resulting message ID so future submissions can edit it.

        The heatmap image will only be generated after the first user submits.
        """
        await interaction.response.defer(thinking=True)

        try:
            # Step 1 – persist the schedule record
            schedule_id = await self.db.create_schedule(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                title=title,
                created_by=interaction.user.id,
            )

            # Step 2 – build embed and view (NO IMAGE YET - live dashboard feel)
            embed = build_schedule_embed(title, participant_count=0)
            view = ScheduleView(schedule_id=schedule_id, db=self.db)

            # Step 3 – send the message WITHOUT an image
            msg = await interaction.followup.send(
                embed=embed,
                view=view,
            )

            # Step 4 – store the message ID for future edits
            await self.db.update_schedule_message_id(schedule_id, msg.id)

            # Re-register the persistent view so the bot can route interactions
            # even after a restart (also registered in bot.py on_ready, but
            # doing it here immediately ensures the view is active right away).
            self.bot.add_view(view)

            logger.info(
                "Schedule created: id=%s title=%r guild=%s channel=%s message=%s",
                schedule_id, title, interaction.guild_id, interaction.channel_id, msg.id,
            )

        except Exception as exc:
            logger.exception("Failed to start schedule: %s", exc)
            await interaction.followup.send(
                f"❌ Failed to create schedule: {exc}", ephemeral=True
            )

    # ------------------------------------------------------------------
    # /schedule view
    # ------------------------------------------------------------------

    @schedule_group.command(
        name="view",
        description="View the latest schedule heatmap adjusted to your timezone.",
    )
    async def schedule_view(self, interaction: discord.Interaction) -> None:
        """
        Finds the most-recently created schedule in the current channel,
        generates a heatmap personalised to the user's timezone, and
        sends it back as an ephemeral message so only they can see it.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # Look for the latest schedule in this channel
            schedules = await self.db.get_schedules_for_channel(interaction.channel_id)
            if not schedules:
                await interaction.followup.send(
                    "⚠️ No schedule found in this channel.  "
                    "Use `/schedule start` to create one.",
                    ephemeral=True,
                )
                return

            schedule = schedules[0]   # most recent
            schedule_id = schedule["id"]

            # Fetch the user's preferred timezone
            tz_name = await self.db.get_user_timezone(interaction.user.id)

            # Generate the personalised heatmap
            grid  = await self.db.get_availability_grid(schedule_id)
            count = await self.db.get_participant_count(schedule_id)

            png_bytes = generate_heatmap(
                grid=grid,
                title=schedule["title"],
                timezone_name=tz_name,
                participant_count=count,
            )

            embed = discord.Embed(
                title=f"📅  {schedule['title']}",
                description=f"Showing availability in **{tz_name}**.",
                colour=discord.Colour.blue(),
            )
            embed.set_image(url="attachment://heatmap.png")
            embed.set_footer(text=f"{count} participant(s)")

            await interaction.followup.send(
                embed=embed,
                file=discord.File(fp=io.BytesIO(png_bytes), filename="heatmap.png"),
                ephemeral=True,
            )

        except Exception as exc:
            logger.exception("Failed to view schedule: %s", exc)
            await interaction.followup.send(
                f"❌ Failed to generate view: {exc}", ephemeral=True
            )

    # ------------------------------------------------------------------
    # /set_timezone <timezone>
    # ------------------------------------------------------------------

    @app_commands.command(
        name="set_timezone",
        description="Set your local timezone for personalised schedule views.",
    )
    @app_commands.describe(
        timezone=(
            "IANA timezone name, e.g. America/New_York, Europe/London, Asia/Tokyo. "
            "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )
    )
    async def set_timezone(
        self, interaction: discord.Interaction, timezone: str
    ) -> None:
        """
        Validates the supplied timezone string against the pytz database and,
        if valid, stores it for the user.
        """
        # Validate the timezone string
        if timezone not in pytz.all_timezones_set:
            # Give the user a helpful hint with similar names
            close_matches = [tz for tz in pytz.all_timezones if timezone.lower() in tz.lower()][:5]
            hint = ""
            if close_matches:
                hint = "\n\nDid you mean one of these?\n" + "\n".join(f"• `{tz}`" for tz in close_matches)

            await interaction.response.send_message(
                f"❌ `{timezone}` is not a recognised IANA timezone.{hint}",
                ephemeral=True,
            )
            return

        await self.db.set_user_timezone(interaction.user.id, timezone)
        await interaction.response.send_message(
            f"✅ Your timezone has been set to **{timezone}**.  "
            "Future `/schedule view` calls will display times in your local timezone.",
            ephemeral=True,
        )
        logger.info("Timezone set: user=%s tz=%s", interaction.user.id, timezone)

    # ------------------------------------------------------------------
    # /help
    # ------------------------------------------------------------------

    @app_commands.command(
        name="help",
        description="Learn how to use TickTock Bot.",
    )
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Display a helpful guide about bot features and workflow."""
        embed = discord.Embed(
            title="📚 TickTock Bot Help",
            description=(
                "**TickTock** helps your team coordinate availability with interactive "
                "schedules and live-updating heatmaps.\n\n"
                "**🔹 Getting Started**\n"
                "1. Use `/schedule start` to create a new availability grid\n"
                "2. Select your available days and hours from the dropdowns\n"
                "3. Click **Submit** to save your availability\n"
                "4. Watch the heatmap update live as teammates respond!\n\n"
            ),
            colour=discord.Colour.blue(),
        )

        embed.add_field(
            name="📅 /schedule start",
            value=(
                "Create a new weekly availability schedule in the current channel. "
                "The bot will post interactive dropdowns for team members to select their available times."
            ),
            inline=False,
        )

        embed.add_field(
            name="👀 /schedule view",
            value=(
                "View the latest schedule in this channel, converted to your personal timezone. "
                "This message is private (only you can see it)."
            ),
            inline=False,
        )

        embed.add_field(
            name="🌍 /set_timezone",
            value=(
                "Set your preferred timezone (e.g., `America/New_York`, `Europe/London`, `Asia/Tokyo`). "
                "This affects how times display when you use `/schedule view`."
            ),
            inline=False,
        )

        embed.add_field(
            name="🔐 /permissions",
            value=(
                "Get the bot invite link with the exact permissions needed. "
                "Share this with server admins for easy setup."
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 Tips",
            value=(
                "• All times are stored in **UTC** but displayed in your timezone\n"
                "• You can update your availability anytime by resubmitting\n"
                "• The heatmap colors show overlap: darker green = more people available\n"
                "• Use 12-hour format (AM/PM) for easier reading"
            ),
            inline=False,
        )

        embed.set_footer(text="Need more help? Contact your server admin or visit our documentation.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /permissions
    # ------------------------------------------------------------------

    @app_commands.command(
        name="permissions",
        description="Get the OAuth2 invite link with required bot permissions.",
    )
    async def permissions_command(self, interaction: discord.Interaction) -> None:
        """Display the bot invite URL with exact permissions needed."""
        if not self.bot.user:
            await interaction.response.send_message(
                "❌ Unable to generate invite link at this time.",
                ephemeral=True,
            )
            return

        # Required permissions:
        # - View Channels (1024)
        # - Send Messages (2048)
        # - Attach Files (32768)
        # - Embed Links (16384)
        # - Use Slash Commands is handled by applications.commands scope
        permissions_int = 1024 + 2048 + 32768 + 16384  # = 52224

        invite_url = (
            f"https://discord.com/api/oauth2/authorize?"
            f"client_id={self.bot.user.id}&permissions={permissions_int}&scope=bot%20applications.commands"
        )

        embed = discord.Embed(
            title="🔐 TickTock Bot Permissions",
            description=(
                "Use this invite link to add TickTock to other servers with the correct permissions.\n\n"
                f"**[Click here to invite TickTock]({invite_url})**"
            ),
            colour=discord.Colour.green(),
        )

        embed.add_field(
            name="Required Permissions",
            value=(
                "✅ **View Channels** - Read channel information\n"
                "✅ **Send Messages** - Post schedules and responses\n"
                "✅ **Attach Files** - Upload heatmap images\n"
                "✅ **Embed Links** - Display rich embeds\n"
                "✅ **Use Slash Commands** - Enable `/schedule` and other commands"
            ),
            inline=False,
        )

        embed.add_field(
            name="Permission Integer",
            value=f"`{permissions_int}` (for manual configuration)",
            inline=False,
        )

        embed.set_footer(text="These are the minimum permissions needed for TickTock to function properly.")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Setup function (required by discord.py's extension loader)
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    """
    Called by ``bot.load_extension('cogs.schedule')``.

    The Database instance is attached to the bot object in bot.py so it can
    be accessed here without circular imports.
    """
    db: Database = bot.db  # type: ignore[attr-defined]
    cog = ScheduleCog(bot, db)

    # Add the cog; this automatically registers all decorated commands
    await bot.add_cog(cog)
    logger.info("ScheduleCog loaded.")

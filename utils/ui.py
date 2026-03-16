"""
utils/ui.py
-----------
Persistent Discord UI components for ScheduleBot.

Components
----------
DaySelect
    Multi-select dropdown listing Monday–Sunday.

HourSelect
    Multi-select dropdown listing 00:00–23:00 in 24-hour format.

SubmitButton
    Triggers availability submission and regenerates the heatmap image.

ScheduleView
    A ``discord.ui.View`` that composes the three components above.
    It is *persistent* (``timeout=None``) so interactions still work
    after a bot restart, provided the view is re-registered on startup.

Custom-ID format
----------------
All component custom_ids embed the schedule_id so the view callback
can identify which schedule is being updated without maintaining
in-memory state:

    schedule:{schedule_id}:days
    schedule:{schedule_id}:hours
    schedule:{schedule_id}:submit

This pattern also future-proofs multi-server use since schedule IDs are
globally unique in our SQLite database.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from utils.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Day dropdown options
# ---------------------------------------------------------------------------

_DAY_OPTIONS = [
    discord.SelectOption(label="Monday",    value="0", emoji="📅"),
    discord.SelectOption(label="Tuesday",   value="1", emoji="📅"),
    discord.SelectOption(label="Wednesday", value="2", emoji="📅"),
    discord.SelectOption(label="Thursday",  value="3", emoji="📅"),
    discord.SelectOption(label="Friday",    value="4", emoji="📅"),
    discord.SelectOption(label="Saturday",  value="5", emoji="🎮"),
    discord.SelectOption(label="Sunday",    value="6", emoji="🎮"),
]

# ---------------------------------------------------------------------------
# Hour dropdown options  (00:00 → 23:00 in 12-hour AM/PM format, max 25 per Discord limit)
# ---------------------------------------------------------------------------

def _format_hour_12h(hour: int) -> str:
    """Convert 24-hour format to 12-hour AM/PM format."""
    if hour == 0:
        return "12:00 AM"
    elif hour < 12:
        return f"{hour}:00 AM"
    elif hour == 12:
        return "12:00 PM"
    else:
        return f"{hour - 12}:00 PM"

_HOUR_OPTIONS = [
    discord.SelectOption(
        label=_format_hour_12h(h),
        value=str(h),
        description=f"{'Morning' if h < 12 else 'Afternoon/Evening'} slot",
    )
    for h in range(24)
]


# ---------------------------------------------------------------------------
# Component classes
# ---------------------------------------------------------------------------

class DaySelect(discord.ui.Select):
    """Multi-select dropdown for choosing days of the week."""

    def __init__(self, schedule_id: int) -> None:
        super().__init__(
            custom_id=f"schedule:{schedule_id}:days",
            placeholder="Select day(s) you are available…",
            min_values=1,
            max_values=7,
            options=_DAY_OPTIONS,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Store the selection in the per-user dict on the parent view.
        view: ScheduleView = self.view  # type: ignore[union-attr]
        uid = interaction.user.id
        view.selections.setdefault(uid, {"days": [], "hours": []})["days"] = [
            int(v) for v in self.values
        ]
        await interaction.response.defer()


class HourSelect(discord.ui.Select):
    """Multi-select dropdown for choosing available hours (00:00–23:00)."""

    def __init__(self, schedule_id: int) -> None:
        super().__init__(
            custom_id=f"schedule:{schedule_id}:hours",
            placeholder="Select hour(s) you are available…",
            min_values=1,
            max_values=24,
            options=_HOUR_OPTIONS,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ScheduleView = self.view  # type: ignore[union-attr]
        uid = interaction.user.id
        view.selections.setdefault(uid, {"days": [], "hours": []})["hours"] = [
            int(v) for v in self.values
        ]
        await interaction.response.defer()


class SubmitButton(discord.ui.Button):
    """
    Saves the user's day/hour selection and regenerates the heatmap.

    Both dropdowns must have been used before submitting; if either is
    empty the bot replies with a helpful error message (ephemeral).
    """

    def __init__(self, schedule_id: int) -> None:
        super().__init__(
            custom_id=f"schedule:{schedule_id}:submit",
            label="✅  Submit / Update My Availability",
            style=discord.ButtonStyle.success,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ScheduleView = self.view  # type: ignore[assignment]
        uid = interaction.user.id

        # Retrieve this user's pending selection
        user_sel = view.selections.get(uid, {})
        selected_days  = user_sel.get("days",  [])
        selected_hours = user_sel.get("hours", [])

        # Validate that the user has made selections in both dropdowns
        if not selected_days:
            await interaction.response.send_message(
                "⚠️ Please select at least one **day** before submitting.",
                ephemeral=True,
            )
            return

        if not selected_hours:
            await interaction.response.send_message(
                "⚠️ Please select at least one **hour** before submitting.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # 1. Persist the user's availability to the database
            await view.db.upsert_availability(
                schedule_id=view.schedule_id,
                user_id=uid,
                days=selected_days,
                hours=selected_hours,
            )

            # 2. Clear the in-memory selection for this user now that it's saved
            view.selections.pop(uid, None)

            # 3. Regenerate the heatmap
            grid = await view.db.get_availability_grid(view.schedule_id)
            count = await view.db.get_participant_count(view.schedule_id)
            schedule = await view.db.get_schedule(view.schedule_id)
            title = schedule["title"] if schedule else "Team Availability"

            from utils.heatmap import generate_heatmap  # local import to avoid circular

            png_bytes = generate_heatmap(
                grid=grid,
                title=title,
                timezone_name="UTC",
                participant_count=count,
            )

            # 4. Edit the original schedule message with the new image
            if interaction.message:
                try:
                    new_file = discord.File(
                        fp=__import__("io").BytesIO(png_bytes),
                        filename="heatmap.png",
                    )
                    embed = interaction.message.embeds[0] if interaction.message.embeds else _build_embed(title, count)
                    embed.set_image(url="attachment://heatmap.png")
                    embed.set_footer(text=f"{count} participant(s) • Timezone: UTC")
                    await interaction.message.edit(embed=embed, attachments=[new_file])
                except discord.Forbidden as forbidden_error:
                    # Handle Discord 403 Forbidden (error code: 50001): Missing Access
                    if forbidden_error.code == 50001:
                        await interaction.followup.send(
                            "❌ **Missing Permissions**\n\n"
                            "I don't have permission to attach files in this channel. "
                            "Please ask a server admin to enable the **Attach Files** permission for me.",
                            ephemeral=True,
                        )
                        logger.warning("Missing 'Attach Files' permission in channel=%s", interaction.channel_id)
                        return
                    else:
                        # Re-raise if it's a different forbidden error
                        raise

            # 5. Acknowledge the user
            days_str  = ", ".join(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d] for d in sorted(selected_days))
            hours_str = ", ".join(_format_hour_12h(h) for h in sorted(selected_hours))
            await interaction.followup.send(
                f"✅ **Availability saved!**\n"
                f"**Days:** {days_str}\n"
                f"**Hours (UTC):** {hours_str}",
                ephemeral=True,
            )

        except Exception as exc:
            logger.exception("Error saving availability for user=%s", uid)
            await interaction.followup.send(
                f"❌ Something went wrong while saving your availability: {exc}",
                ephemeral=True,
            )


# ---------------------------------------------------------------------------
# Composite View
# ---------------------------------------------------------------------------

class ScheduleView(discord.ui.View):
    """
    Persistent view that attaches three UI components to a schedule message.

    Persistence
    -----------
    ``timeout=None`` keeps the view alive indefinitely.  On bot restart,
    re-register the view via ``bot.add_view(ScheduleView(...))`` for every
    active schedule so Discord can route component interactions correctly.

    State
    -----
    ``selections`` is a per-user dict:  ``{user_id: {"days": [...], "hours": [...]}}``

    Each user's in-progress day/hour choices are stored under their own key
    so that two users interacting with the same message simultaneously do not
    overwrite each other's selections.  The dict is cleared for a user after
    they press Submit (data is then durably stored in the database).
    """

    def __init__(self, schedule_id: int, db: "Database") -> None:
        super().__init__(timeout=None)   # persistent — never times out

        self.schedule_id: int = schedule_id
        self.db: "Database" = db

        # Per-user selection buffer: {user_id: {"days": [...], "hours": [...]}}
        self.selections: dict[int, dict[str, list[int]]] = {}

        # Add the three components
        self.add_item(DaySelect(schedule_id))
        self.add_item(HourSelect(schedule_id))
        self.add_item(SubmitButton(schedule_id))


# ---------------------------------------------------------------------------
# Embed builder (shared helper)
# ---------------------------------------------------------------------------

def _build_embed(title: str, participant_count: int = 0) -> discord.Embed:
    """
    Build the schedule embed with placeholder image before any availability
    data has been submitted.
    """
    embed = discord.Embed(
        title=f"📅  {title}",
        description=(
            "**Welcome to TickTock!** 🎯\n\n"
            "Use the dropdowns below to select your available days and hours, "
            "then press **Submit** to save your availability.\n\n"
            "💡 *The heatmap will appear here after the first person submits!*\n\n"
            "All times are stored in **UTC**. Use `/set_timezone` to view "
            "the grid in your local time with `/schedule view`."
        ),
        colour=discord.Colour.green(),
    )
    embed.set_footer(text=f"{participant_count} participant(s) • Timezone: UTC")
    return embed


def build_schedule_embed(title: str, participant_count: int = 0) -> discord.Embed:
    """Public alias used by the schedule cog."""
    return _build_embed(title, participant_count)

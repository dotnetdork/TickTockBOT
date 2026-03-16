"""
utils/database.py
-----------------
Asynchronous SQLite data-access layer for ScheduleBot.

Tables
------
schedules
    Stores each weekly schedule grid created with /schedule start.

availability
    Stores every user's selected day/hour slots (UTC) for a given schedule.

user_timezones
    Stores each user's preferred display timezone (set with /set_timezone).

Architecture note
-----------------
All public methods are async to avoid blocking the Discord event loop.
The `Database` class is designed as a long-lived singleton that is
instantiated once in bot.py and injected into the cogs that need it.

Future expansion
----------------
A `google_calendar_tokens` table can be added here to store OAuth tokens
when the Google Calendar integration is built.
"""

import logging
import os
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_CREATE_SCHEDULES = """
CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    channel_id  INTEGER NOT NULL,
    message_id  INTEGER,            -- filled in after the message is sent
    title       TEXT    NOT NULL,
    created_by  INTEGER NOT NULL,   -- Discord user ID of the creator
    created_at  TEXT    NOT NULL    -- ISO-8601 UTC timestamp
);
"""

_CREATE_AVAILABILITY = """
CREATE TABLE IF NOT EXISTS availability (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),  -- 0=Mon … 6=Sun
    hour        INTEGER NOT NULL CHECK(hour BETWEEN 0 AND 23),         -- UTC hour
    UNIQUE(schedule_id, user_id, day_of_week, hour)
);
"""

_CREATE_USER_TIMEZONES = """
CREATE TABLE IF NOT EXISTS user_timezones (
    user_id  INTEGER PRIMARY KEY,
    timezone TEXT    NOT NULL DEFAULT 'UTC'
);
"""


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    """Async wrapper around an aiosqlite connection."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the database connection and create tables if needed."""
        # Ensure the parent directory exists (e.g. data/)
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)

        self._conn = await aiosqlite.connect(self._db_path)
        # Return rows as sqlite3.Row so they can be accessed by column name
        self._conn.row_factory = aiosqlite.Row

        # Enable foreign-key constraints (off by default in SQLite)
        await self._conn.execute("PRAGMA foreign_keys = ON;")

        # Create tables
        await self._conn.execute(_CREATE_SCHEDULES)
        await self._conn.execute(_CREATE_AVAILABILITY)
        await self._conn.execute(_CREATE_USER_TIMEZONES)
        await self._conn.commit()

        logger.info("Database connected: %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection gracefully."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() has not been called yet.")
        return self._conn

    # ------------------------------------------------------------------
    # schedules table
    # ------------------------------------------------------------------

    async def create_schedule(
        self,
        guild_id: int,
        channel_id: int,
        title: str,
        created_by: int,
    ) -> int:
        """
        Insert a new schedule row and return its auto-generated ID.

        The message_id is left NULL here and filled in later with
        `update_schedule_message_id` once the Discord message has been sent.
        """
        created_at = datetime.now(timezone.utc).isoformat()
        async with self.conn.execute(
            """
            INSERT INTO schedules (guild_id, channel_id, title, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, title, created_by, created_at),
        ) as cursor:
            schedule_id = cursor.lastrowid
        await self.conn.commit()
        logger.debug("Created schedule id=%s title=%r", schedule_id, title)
        return schedule_id

    async def update_schedule_message_id(
        self, schedule_id: int, message_id: int
    ) -> None:
        """Store the Discord message ID once the embed has been posted."""
        await self.conn.execute(
            "UPDATE schedules SET message_id = ? WHERE id = ?",
            (message_id, schedule_id),
        )
        await self.conn.commit()

    async def get_schedule(self, schedule_id: int) -> aiosqlite.Row | None:
        """Fetch a single schedule row by its primary key."""
        async with self.conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_schedule_by_message(
        self, message_id: int
    ) -> aiosqlite.Row | None:
        """
        Look up a schedule by its Discord message ID.
        Used by the persistent View when a button/dropdown interaction fires.
        """
        async with self.conn.execute(
            "SELECT * FROM schedules WHERE message_id = ?", (message_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_schedules_for_channel(
        self, channel_id: int
    ) -> list[aiosqlite.Row]:
        """Return all schedules posted in a given channel, newest first."""
        async with self.conn.execute(
            "SELECT * FROM schedules WHERE channel_id = ? ORDER BY id DESC",
            (channel_id,),
        ) as cursor:
            return await cursor.fetchall()

    # ------------------------------------------------------------------
    # availability table
    # ------------------------------------------------------------------

    async def upsert_availability(
        self,
        schedule_id: int,
        user_id: int,
        days: list[int],
        hours: list[int],
    ) -> None:
        """
        Replace a user's complete availability for a schedule.

        Strategy:
        1. Delete all existing slots for this user on this schedule.
        2. Re-insert the new selection.

        This makes "update" semantics simple: the user always overwrites
        their previous entry with whatever the current selection is.
        """
        async with self.conn.execute(
            "DELETE FROM availability WHERE schedule_id = ? AND user_id = ?",
            (schedule_id, user_id),
        ):
            pass  # deletion is its own statement

        # Build (schedule_id, user_id, day, hour) rows for every combination
        rows = [
            (schedule_id, user_id, day, hour)
            for day in days
            for hour in hours
        ]
        if rows:
            await self.conn.executemany(
                """
                INSERT OR IGNORE INTO availability
                    (schedule_id, user_id, day_of_week, hour)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
        await self.conn.commit()
        logger.debug(
            "Upserted %d slots for user=%s schedule=%s", len(rows), user_id, schedule_id
        )

    async def get_availability_grid(
        self, schedule_id: int
    ) -> dict[tuple[int, int], int]:
        """
        Return a mapping of (day_of_week, hour) -> number_of_users.

        This is the raw data consumed by the heatmap renderer.
        """
        async with self.conn.execute(
            """
            SELECT day_of_week, hour, COUNT(DISTINCT user_id) AS cnt
            FROM availability
            WHERE schedule_id = ?
            GROUP BY day_of_week, hour
            """,
            (schedule_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return {(row["day_of_week"], row["hour"]): row["cnt"] for row in rows}

    async def get_user_availability(
        self, schedule_id: int, user_id: int
    ) -> list[aiosqlite.Row]:
        """Fetch all slots a specific user has set for a schedule."""
        async with self.conn.execute(
            """
            SELECT day_of_week, hour
            FROM availability
            WHERE schedule_id = ? AND user_id = ?
            ORDER BY day_of_week, hour
            """,
            (schedule_id, user_id),
        ) as cursor:
            return await cursor.fetchall()

    async def get_participant_count(self, schedule_id: int) -> int:
        """Return the number of distinct users who have submitted availability."""
        async with self.conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM availability WHERE schedule_id = ?",
            (schedule_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ------------------------------------------------------------------
    # user_timezones table
    # ------------------------------------------------------------------

    async def set_user_timezone(self, user_id: int, timezone: str) -> None:
        """Save (or update) a user's preferred timezone."""
        await self.conn.execute(
            """
            INSERT INTO user_timezones (user_id, timezone)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET timezone = excluded.timezone
            """,
            (user_id, timezone),
        )
        await self.conn.commit()
        logger.debug("Timezone set: user=%s tz=%s", user_id, timezone)

    async def get_user_timezone(self, user_id: int) -> str:
        """
        Return the stored timezone string for a user, or 'UTC' if not set.
        """
        async with self.conn.execute(
            "SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["timezone"] if row else "UTC"

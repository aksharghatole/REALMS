import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .schema import SCHEMA


class Database:
    """Small transaction-aware SQLite gateway used by the engine."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self._migrate_columns()
        self.connection.commit()

    def _migrate_columns(self) -> None:
        migrations = {
            "locations": {"distance": "INTEGER NOT NULL DEFAULT 0", "terrain": "TEXT NOT NULL DEFAULT 'road'", "danger": "INTEGER NOT NULL DEFAULT 0"},
            "characters": {"appearance": "TEXT NOT NULL DEFAULT 'An ordinary-looking traveler.'", "birthplace": "TEXT NOT NULL DEFAULT 'Azure Village'", "hunger": "INTEGER NOT NULL DEFAULT 80", "thirst": "INTEGER NOT NULL DEFAULT 80", "fatigue": "INTEGER NOT NULL DEFAULT 10", "morale": "INTEGER NOT NULL DEFAULT 70", "reputation": "INTEGER NOT NULL DEFAULT 0", "home": "TEXT NOT NULL DEFAULT 'Azure Village'", "short_goal": "TEXT NOT NULL DEFAULT 'Survive and improve your circumstances.'", "ambition": "TEXT NOT NULL DEFAULT 'Live a meaningful life.'", "family_id": "TEXT"},
            "npcs": {"hunger": "INTEGER NOT NULL DEFAULT 80", "fatigue": "INTEGER NOT NULL DEFAULT 10", "routine": "TEXT NOT NULL DEFAULT 'work'", "ambition": "TEXT NOT NULL DEFAULT 'Make a better life.'", "personality": "TEXT NOT NULL DEFAULT 'ordinary, cautious'", "goals": "TEXT NOT NULL DEFAULT 'Make a better life.'", "fears": "TEXT NOT NULL DEFAULT 'poverty'", "social_status": "TEXT NOT NULL DEFAULT 'Villager'", "culture_id": "TEXT NOT NULL DEFAULT 'Azure'", "importance_level": "INTEGER NOT NULL DEFAULT 2"},
            "cultivation_states": {
                "realm_name": "TEXT NOT NULL DEFAULT 'Body Tempering'",
                "foundation_damage": "INTEGER NOT NULL DEFAULT 0",
                "foundation_stability": "INTEGER NOT NULL DEFAULT 100",
                "tribulation_spotting_points": "INTEGER NOT NULL DEFAULT 0",
                "tribulation_prediction": "TEXT NOT NULL DEFAULT ''",
            },
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, tuple(params))
        self.connection.commit()
        return cursor

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> None:
        self.connection.executemany(sql, rows)
        self.connection.commit()

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.connection.execute(sql, tuple(params)).fetchall()

    def close(self) -> None:
        self.connection.close()
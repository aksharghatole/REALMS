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
            "world_state": {"universe_id": "TEXT", "current_epoch": "TEXT", "current_year": "INTEGER", "current_month": "INTEGER", "current_day": "INTEGER", "current_hour": "INTEGER", "world_condition": "TEXT", "stability": "INTEGER", "population_estimate": "INTEGER", "major_civilizations": "INTEGER", "active_wars": "INTEGER", "active_disasters": "INTEGER", "major_discoveries": "INTEGER", "major_historical_events": "INTEGER", "major_faction_changes": "INTEGER", "economic_conditions": "TEXT", "cultivation_environment": "TEXT", "spiritual_energy_conditions": "TEXT", "celestial_events": "TEXT"},
            "universes": {"name": "TEXT NOT NULL", "seed": "INTEGER NOT NULL DEFAULT 0", "age": "INTEGER NOT NULL DEFAULT 5000", "creation_time": "TEXT NOT NULL DEFAULT 'unknown'", "current_time": "TEXT NOT NULL DEFAULT 'unknown'", "physical_ruleset": "TEXT NOT NULL DEFAULT 'standard'", "cultivation_ruleset": "TEXT NOT NULL DEFAULT 'mixed'", "stability": "INTEGER NOT NULL DEFAULT 80", "civilization_count": "INTEGER NOT NULL DEFAULT 0", "galaxy_count_estimate": "INTEGER NOT NULL DEFAULT 1", "known_regions": "TEXT NOT NULL DEFAULT ''"},
            "galaxies": {"universe_id": "TEXT NOT NULL", "seed": "INTEGER NOT NULL DEFAULT 0", "type": "TEXT NOT NULL DEFAULT 'spiral'", "estimated_star_count": "INTEGER NOT NULL DEFAULT 100", "age": "INTEGER NOT NULL DEFAULT 5000", "metallicity": "INTEGER NOT NULL DEFAULT 50", "dominant_civilizations": "TEXT NOT NULL DEFAULT ''", "known_systems": "TEXT NOT NULL DEFAULT ''"},
            "star_systems": {"galaxy_id": "TEXT NOT NULL", "name": "TEXT NOT NULL", "seed": "INTEGER NOT NULL DEFAULT 0", "star_type": "TEXT NOT NULL DEFAULT 'yellow dwarf'", "planet_count": "INTEGER NOT NULL DEFAULT 1", "habitability": "TEXT NOT NULL DEFAULT 'habitable'", "exploration_status": "TEXT NOT NULL DEFAULT 'unknown'", "discovered": "INTEGER NOT NULL DEFAULT 0"},
            "stars": {"system_id": "TEXT NOT NULL", "name": "TEXT NOT NULL", "type": "TEXT NOT NULL DEFAULT 'yellow dwarf'", "mass": "REAL NOT NULL DEFAULT 1.0", "radius": "REAL NOT NULL DEFAULT 1.0", "temperature": "INTEGER NOT NULL DEFAULT 5800", "age": "INTEGER NOT NULL DEFAULT 5000", "luminosity": "REAL NOT NULL DEFAULT 1.0", "metallicity": "INTEGER NOT NULL DEFAULT 50", "lifetime_stage": "TEXT NOT NULL DEFAULT 'main sequence'"},
            "planets": {"world_id": "TEXT", "system_id": "TEXT", "seed": "INTEGER NOT NULL DEFAULT 0", "planet_type": "TEXT NOT NULL DEFAULT 'terrestrial'", "size": "INTEGER NOT NULL DEFAULT 1", "gravity": "REAL NOT NULL DEFAULT 1.0", "atmosphere": "TEXT NOT NULL DEFAULT 'breathable'", "climate": "TEXT NOT NULL DEFAULT 'temperate'", "temperature": "INTEGER NOT NULL DEFAULT 20", "water": "INTEGER NOT NULL DEFAULT 50", "resources": "TEXT NOT NULL DEFAULT ''", "biosphere": "TEXT NOT NULL DEFAULT 'none'", "population": "INTEGER NOT NULL DEFAULT 0", "technology_level": "INTEGER NOT NULL DEFAULT 0", "cultivation_environment": "TEXT NOT NULL DEFAULT 'ordinary'", "civilizations": "INTEGER NOT NULL DEFAULT 0", "political_status": "TEXT NOT NULL DEFAULT 'unclaimed'", "exploration_status": "TEXT NOT NULL DEFAULT 'unknown'", "habitat_state": "TEXT NOT NULL DEFAULT 'habitable'", "created_year": "INTEGER NOT NULL DEFAULT 1"},
            "spacecraft": {"owner_id": "TEXT", "ship_type": "TEXT NOT NULL DEFAULT 'exploration vessel'", "hull": "INTEGER NOT NULL DEFAULT 100", "engine": "INTEGER NOT NULL DEFAULT 1", "speed": "INTEGER NOT NULL DEFAULT 1", "range": "INTEGER NOT NULL DEFAULT 10", "fuel": "INTEGER NOT NULL DEFAULT 50", "cargo_capacity": "INTEGER NOT NULL DEFAULT 10", "passenger_capacity": "INTEGER NOT NULL DEFAULT 2", "crew_capacity": "INTEGER NOT NULL DEFAULT 4", "life_support": "INTEGER NOT NULL DEFAULT 80", "sensors": "INTEGER NOT NULL DEFAULT 50", "weapons": "INTEGER NOT NULL DEFAULT 0", "defenses": "INTEGER NOT NULL DEFAULT 0", "technology": "INTEGER NOT NULL DEFAULT 0", "condition": "INTEGER NOT NULL DEFAULT 100", "current_location": "TEXT NOT NULL DEFAULT 'docked'"},
            "space_routes": {"route_type": "TEXT NOT NULL DEFAULT 'trade'", "origin": "TEXT NOT NULL", "destination": "TEXT NOT NULL", "distance": "INTEGER NOT NULL DEFAULT 1", "danger": "INTEGER NOT NULL DEFAULT 0", "status": "TEXT NOT NULL DEFAULT 'active'", "cargo_capacity": "INTEGER NOT NULL DEFAULT 0", "travel_time": "INTEGER NOT NULL DEFAULT 1"},
            "space_journeys": {"ship_id": "TEXT NOT NULL", "route_id": "TEXT NOT NULL", "status": "TEXT NOT NULL DEFAULT 'launched'", "progress": "INTEGER NOT NULL DEFAULT 0", "fuel_cost": "INTEGER NOT NULL DEFAULT 0", "launched_day": "INTEGER NOT NULL DEFAULT 1", "eta_days": "INTEGER NOT NULL DEFAULT 1"},
            "space_cargo": {"ship_id": "TEXT NOT NULL", "good": "TEXT NOT NULL", "quantity": "INTEGER NOT NULL DEFAULT 1", "value": "INTEGER NOT NULL DEFAULT 0", "origin": "TEXT NOT NULL", "destination": "TEXT NOT NULL", "status": "TEXT NOT NULL DEFAULT 'loaded'"},
            "space_stations": {"system_id": "TEXT NOT NULL", "name": "TEXT NOT NULL", "station_type": "TEXT NOT NULL DEFAULT 'orbital station'", "owner_id": "TEXT", "location": "TEXT NOT NULL DEFAULT 'orbit'", "capacity": "INTEGER NOT NULL DEFAULT 100", "status": "TEXT NOT NULL DEFAULT 'active'"},
            "colony": {"world_id": "TEXT", "planet_id": "TEXT", "name": "TEXT NOT NULL", "founder": "TEXT NOT NULL DEFAULT 'unknown'", "population": "INTEGER NOT NULL DEFAULT 0", "infrastructure": "INTEGER NOT NULL DEFAULT 0", "development": "TEXT NOT NULL DEFAULT 'outpost'", "government": "TEXT NOT NULL DEFAULT 'none'", "economy": "TEXT NOT NULL DEFAULT 'survival'", "dependency": "TEXT NOT NULL DEFAULT 'parent'", "status": "TEXT NOT NULL DEFAULT 'active'"},
            "organizations": {
                "founder_id": "TEXT",
                "founded_date": "TEXT",
                "parent_organization_id": "TEXT",
                "headquarters": "TEXT",
                "territory": "TEXT",
                "leader_id": "TEXT",
                "leadership_structure": "TEXT NOT NULL DEFAULT 'single_leader'",
                "members": "TEXT NOT NULL DEFAULT '0'",
                "assets": "TEXT NOT NULL DEFAULT ''",
                "income": "INTEGER NOT NULL DEFAULT 0",
                "expenses": "INTEGER NOT NULL DEFAULT 0",
                "debts": "INTEGER NOT NULL DEFAULT 0",
                "legitimacy": "INTEGER NOT NULL DEFAULT 50",
                "ideology": "TEXT NOT NULL DEFAULT 'pragmatic'",
                "culture": "TEXT NOT NULL DEFAULT 'balanced'",
                "goals": "TEXT NOT NULL DEFAULT 'survive'",
                "policies": "TEXT NOT NULL DEFAULT ''",
                "laws": "TEXT NOT NULL DEFAULT ''",
                "rivals": "TEXT NOT NULL DEFAULT ''",
                "allies": "TEXT NOT NULL DEFAULT ''",
                "dependencies": "TEXT NOT NULL DEFAULT ''",
                "technology_level": "INTEGER NOT NULL DEFAULT 0",
                "cultivation_strength": "INTEGER NOT NULL DEFAULT 0",
                "military_strength": "INTEGER NOT NULL DEFAULT 0",
                "economic_strength": "INTEGER NOT NULL DEFAULT 0",
                "research_strength": "INTEGER NOT NULL DEFAULT 0",
                "stability": "INTEGER NOT NULL DEFAULT 50",
                "morale": "INTEGER NOT NULL DEFAULT 50",
                "corruption": "INTEGER NOT NULL DEFAULT 0",
                "succession_rules": "TEXT NOT NULL DEFAULT 'none'",
                "historical_events": "TEXT NOT NULL DEFAULT ''",
                "influence": "INTEGER NOT NULL DEFAULT 0",
            },
            "organization_members": {
                "role": "TEXT NOT NULL DEFAULT 'member'",
                "joined_date": "TEXT",
                "status": "TEXT NOT NULL DEFAULT 'active'",
                "contribution": "INTEGER NOT NULL DEFAULT 0",
                "loyalty": "INTEGER NOT NULL DEFAULT 50",
                "reputation": "INTEGER NOT NULL DEFAULT 0",
                "permissions": "TEXT NOT NULL DEFAULT 'basic'",
                "responsibilities": "TEXT NOT NULL DEFAULT ''",
                "salary": "INTEGER NOT NULL DEFAULT 0",
                "benefits": "TEXT NOT NULL DEFAULT ''",
                "relationships": "TEXT NOT NULL DEFAULT ''",
                "disciplinary_history": "TEXT NOT NULL DEFAULT ''",
            },
            "military_units": {
                "owner_id": "TEXT",
                "organization_id": "TEXT",
                "commander_id": "TEXT",
                "unit_type": "TEXT NOT NULL DEFAULT 'infantry'",
                "size": "INTEGER NOT NULL DEFAULT 100",
                "manpower": "INTEGER NOT NULL DEFAULT 100",
                "trained_manpower": "INTEGER NOT NULL DEFAULT 80",
                "equipment": "TEXT NOT NULL DEFAULT 'standard'",
                "weapons": "TEXT NOT NULL DEFAULT 'spear'",
                "armor": "TEXT NOT NULL DEFAULT 'cloth'",
                "cultivation_strength": "INTEGER NOT NULL DEFAULT 0",
                "technology_level": "INTEGER NOT NULL DEFAULT 0",
                "morale": "INTEGER NOT NULL DEFAULT 50",
                "experience": "INTEGER NOT NULL DEFAULT 0",
                "discipline": "INTEGER NOT NULL DEFAULT 50",
                "readiness": "INTEGER NOT NULL DEFAULT 60",
                "supplies": "INTEGER NOT NULL DEFAULT 60",
                "ammunition": "INTEGER NOT NULL DEFAULT 50",
                "fuel": "INTEGER NOT NULL DEFAULT 0",
                "medical_capacity": "INTEGER NOT NULL DEFAULT 10",
                "movement_speed": "INTEGER NOT NULL DEFAULT 1",
                "mobility": "INTEGER NOT NULL DEFAULT 50",
                "terrain_specialization": "TEXT NOT NULL DEFAULT 'plains'",
                "communication": "INTEGER NOT NULL DEFAULT 50",
                "intelligence": "INTEGER NOT NULL DEFAULT 40",
                "loyalty": "INTEGER NOT NULL DEFAULT 60",
                "fatigue": "INTEGER NOT NULL DEFAULT 0",
                "casualties": "INTEGER NOT NULL DEFAULT 0",
                "victories": "INTEGER NOT NULL DEFAULT 0",
                "defeats": "INTEGER NOT NULL DEFAULT 0",
                "history": "TEXT NOT NULL DEFAULT ''",
                "status": "TEXT NOT NULL DEFAULT 'ready'",
            },
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
            if not existing:
                continue
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
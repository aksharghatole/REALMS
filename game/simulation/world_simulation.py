import random
import uuid

from game.clock import GameDate


PLANET_TYPES = (
    "Mortal World",
    "Cultivation World",
    "Beast World",
    "Machine World",
    "Ruined World",
    "Dead World",
    "Ocean World",
    "Desert World",
    "Frozen World",
    "Spirit World",
    "Demon World",
    "Immortal World",
    "Ancient World",
    "Artificial World",
    "Fragmented World",
    "Sealed World",
    "Forbidden World",
    "Unknown World",
)


class WorldSimulation:
    """Lightweight but persistent world simulation for major political and economic changes."""

    def __init__(self, db, seed: int = 184729):
        self.db = db
        self.seed = seed

    def ensure_world_state(self, world_id: str) -> dict:
        existing = self.db.one("SELECT * FROM world_state WHERE world_id = ?", (world_id,))
        if existing is not None:
            return dict(existing)
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        rng = random.Random(self.seed + world["seed"])
        state = {
            "world_id": world_id,
            "universe_id": f"universe:{world['seed']}",
            "current_epoch": "Age of Mortals",
            "current_year": world["year"],
            "current_month": world["month"],
            "current_day": world["day"],
            "current_hour": world["hour"],
            "world_condition": "stable",
            "stability": 75,
            "population_estimate": 250000,
            "major_civilizations": 3,
            "active_wars": 0,
            "active_disasters": 0,
            "major_discoveries": 0,
            "major_historical_events": 0,
            "major_faction_changes": 0,
            "economic_conditions": "balanced",
            "cultivation_environment": "ordinary",
            "spiritual_energy_conditions": "mild",
            "celestial_events": "quiet",
        }
        self.db.execute(
            "INSERT INTO world_state (world_id, universe_id, current_epoch, current_year, current_month, current_day, current_hour, world_condition, stability, population_estimate, major_civilizations, active_wars, active_disasters, major_discoveries, major_historical_events, major_faction_changes, economic_conditions, cultivation_environment, spiritual_energy_conditions, celestial_events) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                state["world_id"],
                state["universe_id"],
                state["current_epoch"],
                state["current_year"],
                state["current_month"],
                state["current_day"],
                state["current_hour"],
                state["world_condition"],
                state["stability"],
                state["population_estimate"],
                state["major_civilizations"],
                state["active_wars"],
                state["active_disasters"],
                state["major_discoveries"],
                state["major_historical_events"],
                state["major_faction_changes"],
                state["economic_conditions"],
                state["cultivation_environment"],
                state["spiritual_energy_conditions"],
                state["celestial_events"],
            ),
        )
        return state

    def ensure_planet(self, world_id: str, name: str) -> dict:
        row = self.db.one("SELECT * FROM planets WHERE world_id = ? AND name = ?", (world_id, name))
        if row is not None:
            return dict(row)
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        planet_seed = sum((ord(ch) + index) for index, ch in enumerate(name)) + world["seed"]
        rng = random.Random(planet_seed)
        planet_type = PLANET_TYPES[rng.randrange(len(PLANET_TYPES))]
        planet_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"planet:{world_id}:{name}"))
        planet = {
            "planet_id": planet_id,
            "world_id": world_id,
            "name": name,
            "planet_type": planet_type,
            "size": rng.randint(1, 10),
            "gravity": round(rng.uniform(0.5, 1.8), 2),
            "atmosphere": rng.choice(("thin", "breathable", "dense", "toxic")),
            "climate": rng.choice(("temperate", "arid", "frozen", "humid", "stormy")),
            "spiritual_energy_density": rng.randint(0, 100),
            "elemental_affinity": rng.choice(("fire", "water", "wind", "earth", "void", "wood", "lightning")),
            "resources": rng.choice(("ore, grain, herbs", "spirit stones, herbs, crystals", "food, wood, stone, metals", "artifact ruins, ancient crystals")),
            "dominant_species": rng.choice(("Human", "Beast", "Spirit", "Demon", "Ancient Beast", "Voidborn")),
            "civilizations": rng.randint(1, 6),
            "cultivation_ceiling": rng.randint(2, 12),
            "technological_development": rng.randint(1, 10),
            "magical_traditions": rng.choice(("sect-based", "ritualistic", "ancestral", "elemental", "none")),
            "dangerous_regions": rng.randint(0, 5),
            "major_religions": rng.choice(("faith of the hearth", "discipline of heaven", "ancestor worship", "astral doctrine")),
            "political_structures": rng.choice(("kingdom", "clan confederation", "merchant republic", "theocracy", "tribal union")),
            "trade_relationships": rng.randint(0, 8),
            "environmental_stability": rng.randint(40, 95),
            "celestial_phenomena": rng.choice(("quiet orbit", "meteor showers", "spirit tide", "lunar eclipse")),
        }
        self.db.execute(
            "INSERT INTO planets (planet_id, world_id, name, planet_type, size, gravity, atmosphere, climate, spiritual_energy_density, elemental_affinity, resources, dominant_species, civilizations, cultivation_ceiling, technological_development, magical_traditions, dangerous_regions, major_religions, political_structures, trade_relationships, environmental_stability, celestial_phenomena) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                planet["planet_id"],
                planet["world_id"],
                planet["name"],
                planet["planet_type"],
                planet["size"],
                planet["gravity"],
                planet["atmosphere"],
                planet["climate"],
                planet["spiritual_energy_density"],
                planet["elemental_affinity"],
                planet["resources"],
                planet["dominant_species"],
                planet["civilizations"],
                planet["cultivation_ceiling"],
                planet["technological_development"],
                planet["magical_traditions"],
                planet["dangerous_regions"],
                planet["major_religions"],
                planet["political_structures"],
                planet["trade_relationships"],
                planet["environmental_stability"],
                planet["celestial_phenomena"],
            ),
        )
        return planet

    def create_war(self, world_id: str, attacker: str, defender: str, cause: str) -> dict:
        war_id = str(uuid.uuid4())
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        war = {
            "war_id": war_id,
            "world_id": world_id,
            "attacker": attacker,
            "defender": defender,
            "cause": cause,
            "status": "Tension",
            "phase": "Tension",
            "start_year": world["year"],
            "start_month": world["month"],
            "start_day": world["day"],
            "territory_contested": "borderland",
            "military_strength": 50,
            "casualties": 0,
            "morale": 50,
            "supply": 50,
            "allies": "",
            "peace_conditions": "",
            "result": "ongoing",
        }
        self.db.execute(
            "INSERT INTO wars (war_id, world_id, attacker, defender, cause, status, phase, start_year, start_month, start_day, territory_contested, military_strength, casualties, morale, supply, allies, peace_conditions, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                war["war_id"],
                war["world_id"],
                war["attacker"],
                war["defender"],
                war["cause"],
                war["status"],
                war["phase"],
                war["start_year"],
                war["start_month"],
                war["start_day"],
                war["territory_contested"],
                war["military_strength"],
                war["casualties"],
                war["morale"],
                war["supply"],
                war["allies"],
                war["peace_conditions"],
                war["result"],
            ),
        )
        self.db.execute(
            "INSERT INTO events (event_id, world_id, character_id, kind, text, year, month, day, importance) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), world_id, "war", f"{attacker} and {defender} have entered a new war over {cause}.", world["year"], world["month"], world["day"], 4),
        )
        return war

    def simulate(self, world_id: str, days: int = 30) -> bool:
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        state = self.ensure_world_state(world_id)
        if days <= 0:
            return True
        current = GameDate(world["year"], world["month"], world["day"], world["hour"])
        end = current.advance(days * 24)
        self.db.execute(
            "UPDATE worlds SET year = ?, month = ?, day = ?, hour = ? WHERE world_id = ?",
            (end.year, end.month, end.day, end.hour, world_id),
        )
        self.db.execute(
            "UPDATE world_state SET current_year = ?, current_month = ?, current_day = ?, current_hour = ?, active_wars = ?, stability = ?, economic_conditions = ?, cultivation_environment = ?, spiritual_energy_conditions = ? WHERE world_id = ?",
            (
                end.year,
                end.month,
                end.day,
                end.hour,
                self.db.one("SELECT COUNT(*) AS count FROM wars WHERE world_id = ? AND result = 'ongoing'", (world_id,))["count"],
                max(0, min(100, state["stability"] + (days // 10) - 2)),
                "mixed" if days > 14 else "balanced",
                "ordinary" if days < 20 else "heightened",
                "mild" if days < 15 else "unstable",
                world_id,
            ),
        )
        if days >= 14:
            self.db.execute(
                "INSERT INTO events (event_id, world_id, character_id, kind, text, year, month, day, importance) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), world_id, "world", "The wider world turns more volatile as trade, labor, and rumors shift across the region.", end.year, end.month, end.day, 3),
            )
        return True

    def world_news(self, world_id: str) -> list[str]:
        items = self.db.all(
            "SELECT text, kind, year, month, day FROM events WHERE world_id = ? AND kind IN ('world', 'war', 'cultivation', 'politics', 'economy', 'disaster') ORDER BY rowid DESC LIMIT 12",
            (world_id,),
        )
        return [f"{row['year']}/{row['month']}/{row['day']} — {row['text']}" for row in items]

import json
import random
import uuid
from pathlib import Path

from game.actions import Action, parse_command
from game.biology import default_species_record, inherit_traits_for_new_character, mutation_effect
from game.clock import GameDate
from game.cultivation.realms import breakthrough, realm_name
from game.cultivation.system import CultivationEngine
from game.cultivation.tribulations import TribulationEngine
from game.database.db import Database
from game.narrative import action_message
from game.simulation.world_tick import WorldTick
from game.simulation.situations import SituationEngine
from game.world.generator import WorldGenerator
from game.achievements import INITIAL_ACHIEVEMENTS
from game.ai.conversation import ConversationService
from game.ai.provider import AIProvider, configured_provider
from game.combat.combat import Combat, Combatant
from game.cultivation.realms import realm_power
from game.economy.economic_engine import EconomicEngine
from game.transport.transport_engine import TransportEngine


class GameEngine:
    """Authoritative application service for worlds, characters, and actions."""

    def __init__(self, database: Database, seed: int = 184729, provider: AIProvider | None = None):
        self.db = database
        self.seed = seed
        self.tick = WorldTick(database, seed)
        self.situations = SituationEngine(database, seed)
        self.provider = provider or configured_provider()
        self.conversations = ConversationService(database, seed, self.provider)
        self.cultivation = CultivationEngine(database, seed)
        self.tribulations = TribulationEngine(database, seed)
        self.economy = EconomicEngine(database, self.date, self.log)
        self.transport = TransportEngine(database, self.date)
        self.tick.economic_step = self.economy.simulate
        self.tick.transport_step = self.transport.step
        self.active_combats: dict[str, Combat] = {}

    @classmethod
    def open(cls, path: str | Path, seed: int = 184729) -> "GameEngine":
        return cls(Database(path), seed)

    def create_world(self, name: str = "Azure Heaven") -> str:
        existing = self.db.one("SELECT world_id FROM worlds LIMIT 1")
        if existing:
            self.seed_npc_brains(existing["world_id"])
            return existing["world_id"]
        world_id = WorldGenerator(self.db).create(self.seed, name)
        self.db.executemany("INSERT OR IGNORE INTO achievements VALUES (?, ?, ?, ?, ?)", ((str(uuid.uuid5(uuid.NAMESPACE_DNS, f'achievement:{code}')), code, title, description, category) for code, title, description, category in INITIAL_ACHIEVEMENTS))
        self.seed_npc_brains(world_id)
        return world_id

    def seed_npc_brains(self, world_id: str) -> None:
        date = self.date(world_id)
        for npc in self.db.all("SELECT npc_id, name, profession FROM npcs WHERE world_id = ?", (world_id,)):
            self.db.execute("INSERT OR IGNORE INTO npc_emotions (npc_id) VALUES (?)", (npc["npc_id"],))
            knowledge = {"Farmer": ("village", "The fields and irrigation channels around Azure Village."), "Merchant": ("market", "The Eastern Market and its ordinary prices."), "Blacksmith": ("workshop", "Iron, tools, and the craftspeople of the village."), "Guard": ("roads", "The roads near Azure Village and common travelers."), "Doctor": ("herbs", "Common herbs and local illnesses."), "Scholar": ("history", "Old stories and records kept near the village."), "Sect Servant": ("sect", "The daily routines of Cloudstep Sect.")}.get(npc["profession"], ("village", "Ordinary news from Azure Village."))
            if self.db.one("SELECT knowledge_id FROM npc_knowledge WHERE npc_id = ? LIMIT 1", (npc["npc_id"],)) is None:
                self.db.execute("INSERT INTO npc_knowledge VALUES (?, ?, ?, ?, ?, ?, 80, ?, 'fact')", (str(uuid.uuid4()), world_id, npc["npc_id"], knowledge[0], knowledge[1], "experience", date.day_of_year))

    def create_species(self, name: str, classification: str = "humanoid", parent_species: str | None = None, origin: str = "Azure Heaven", average_lifespan: int = 80, cultivation_affinity: str = "balanced", **kwargs) -> dict:
        if not name or not name.strip():
            raise ValueError("Species name is required")
        record = default_species_record(name.strip(), classification=classification, parent_species=parent_species, origin=origin, average_lifespan=average_lifespan, cultivation_affinity=cultivation_affinity, **kwargs)
        existing = self.db.one("SELECT * FROM species WHERE name = ?", (record["name"],))
        if existing:
            return dict(existing)
        world_row = self.db.one("SELECT world_id, year FROM worlds LIMIT 1")
        created_year = world_row["year"] if world_row else 1
        species_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO species (species_id, name, classification, parent_species, origin, biological_traits, average_lifespan, maturity_age, reproduction_model, environmental_preferences, physical_capabilities, intelligence_range, cultivation_affinity, technological_affinity, population, rarity, extinction_status, created_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                species_id,
                record["name"],
                record["classification"],
                record.get("parent_species"),
                record["origin"],
                json.dumps(record.get("biological_traits", {}), sort_keys=True),
                record.get("average_lifespan", 80),
                record.get("maturity_age", 18),
                record.get("reproduction_model", "sexual"),
                json.dumps(record.get("environmental_preferences", []), sort_keys=True),
                json.dumps(record.get("physical_capabilities", []), sort_keys=True),
                json.dumps(record.get("intelligence_range", [0, 100]), sort_keys=True),
                record.get("cultivation_affinity", "balanced"),
                record.get("technological_affinity", "moderate"),
                record.get("population", 1),
                record.get("rarity", "common"),
                record.get("extinction_status", "living"),
                created_year,
            ),
        )
        return dict(self.db.one("SELECT * FROM species WHERE species_id = ?", (species_id,)))

    def create_universe(self, name: str = "Azure Universe", seed: int = 184729) -> dict:
        universe_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO universes (universe_id, name, seed, age, creation_time, current_time, physical_ruleset, cultivation_ruleset, stability, civilization_count, galaxy_count_estimate, known_regions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (universe_id, name, seed, 5000, "Unknown", "Unknown", "standard", "mixed", 80, 0, 1, ""))
        return dict(self.db.one("SELECT * FROM universes WHERE universe_id = ?", (universe_id,)))

    def create_galaxy(self, universe_id: str, galaxy_type: str = "spiral", seed: int | None = None) -> dict:
        universe = self.db.one("SELECT * FROM universes WHERE universe_id = ?", (universe_id,))
        if universe is None:
            raise ValueError("Unknown universe")
        seed = seed if seed is not None else (universe["seed"] + len(self.db.all("SELECT galaxy_id FROM galaxies")))
        galaxy_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO galaxies (galaxy_id, universe_id, seed, type, estimated_star_count, age, metallicity, dominant_civilizations, known_systems) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (galaxy_id, universe_id, seed, galaxy_type, 120, 5000, 50, "", ""))
        return dict(self.db.one("SELECT * FROM galaxies WHERE galaxy_id = ?", (galaxy_id,)))

    def create_star_system(self, galaxy_id: str, name: str, star_type: str = "yellow dwarf") -> dict:
        galaxy = self.db.one("SELECT * FROM galaxies WHERE galaxy_id = ?", (galaxy_id,))
        if galaxy is None:
            raise ValueError("Unknown galaxy")
        existing = self.db.one("SELECT * FROM star_systems WHERE galaxy_id = ? AND name = ?", (galaxy_id, name))
        if existing:
            return dict(existing)
        system_id = str(uuid.uuid4())
        seed = galaxy["seed"] + sum((ord(ch) + index) for index, ch in enumerate(name))
        self.db.execute("INSERT INTO star_systems (system_id, galaxy_id, name, seed, star_type, planet_count, habitability, exploration_status, discovered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (system_id, galaxy_id, name, seed, star_type, 1, "habitable", "unknown", 0))
        star_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO stars (star_id, system_id, name, type, mass, radius, temperature, age, luminosity, metallicity, lifetime_stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (star_id, system_id, name, star_type, 1.0, 1.0, 5800, 5000, 1.0, 50, "main sequence"))
        return dict(self.db.one("SELECT * FROM star_systems WHERE system_id = ?", (system_id,)))

    def create_planet(self, system_id: str, name: str, planet_type: str = "terrestrial", world_id: str | None = None) -> dict:
        system = self.db.one("SELECT * FROM star_systems WHERE system_id = ?", (system_id,))
        if system is None:
            raise ValueError("Unknown system")
        existing = self.db.one("SELECT * FROM planets WHERE system_id = ? AND name = ?", (system_id, name))
        if existing:
            return dict(existing)
        seed = system["seed"] + sum((ord(ch) + index) for index, ch in enumerate(name))
        rng = random.Random(seed)
        planet_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO planets (planet_id, world_id, system_id, seed, name, planet_type, size, gravity, atmosphere, climate, temperature, water, resources, biosphere, population, technology_level, cultivation_environment, civilizations, political_status, exploration_status, habitat_state, created_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                planet_id,
                world_id,
                system_id,
                seed,
                name,
                planet_type,
                rng.randint(1, 10),
                round(rng.uniform(0.4, 1.8), 2),
                rng.choice(("breathable", "thin", "toxic", "dense", "vacuum")),
                rng.choice(("temperate", "arid", "frozen", "humid", "stormy")),
                rng.randint(-80, 40),
                rng.randint(5, 95),
                rng.choice(("metals, water", "spirit crystals, herbs", "grain, minerals, rare earths", "energy, silicon, metals")),
                rng.choice(("rich", "sparse", "none", "abundant")),
                rng.randint(0, 500000),
                rng.randint(0, 9),
                rng.choice(("ordinary", "high spirit", "low spirit", "elemental", "void")),
                rng.randint(0, 3),
                rng.choice(("unclaimed", "tribal", "kingdom", "empire")),
                "unknown",
                "habitable" if rng.random() > 0.2 else "barely_habitable",
                1,
            ),
        )
        return dict(self.db.one("SELECT * FROM planets WHERE planet_id = ?", (planet_id,)))

    def create_spacecraft(self, name: str, owner_id: str | None = None, ship_type: str = "exploration vessel", current_location: str = "docked") -> dict:
        ship_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO spacecraft (ship_id, name, owner_id, ship_type, hull, engine, speed, range, fuel, cargo_capacity, passenger_capacity, crew_capacity, life_support, sensors, weapons, defenses, technology, condition, current_location) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (ship_id, name, owner_id, ship_type, 100, 1, 8, 20, 50, 20, 6, 8, 80, 60, 0, 0, 1, 100, current_location))
        return dict(self.db.one("SELECT * FROM spacecraft WHERE ship_id = ?", (ship_id,)))

    def create_space_route(self, route_type: str, origin: str, destination: str, distance: int = 1, danger: int = 0) -> dict:
        route_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO space_routes (route_id, route_type, origin, destination, distance, danger, status, cargo_capacity, travel_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (route_id, route_type, origin, destination, distance, danger, "active", 10, max(1, distance // 2)))
        return dict(self.db.one("SELECT * FROM space_routes WHERE route_id = ?", (route_id,)))

    def launch_spacecraft(self, ship_id: str, route_id: str, fuel: int = 5) -> dict:
        ship = self.db.one("SELECT * FROM spacecraft WHERE ship_id = ?", (ship_id,))
        route = self.db.one("SELECT * FROM space_routes WHERE route_id = ?", (route_id,))
        if ship is None or route is None:
            raise ValueError("Unknown ship or route")
        journey_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO space_journeys (journey_id, ship_id, route_id, status, progress, fuel_cost, launched_day, eta_days) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (journey_id, ship_id, route_id, "launched", 0, max(1, fuel), 1, max(1, route["travel_time"])))
        self.db.execute("UPDATE spacecraft SET fuel = MAX(0, fuel - ?), current_location = ? WHERE ship_id = ?", (max(1, fuel), route["destination"], ship_id))
        return dict(self.db.one("SELECT * FROM space_journeys WHERE journey_id = ?", (journey_id,)))

    def species_for_character(self, character_id: str) -> dict:
        character = dict(self.character(character_id))
        species_name = character.get("species") or "Human"
        row = self.db.one("SELECT * FROM species WHERE name = ?", (species_name,))
        if row is None:
            return self.create_species(species_name, origin=character.get("origin", "Azure Heaven"))
        return dict(row)

    def bloodline_for_character(self, character_id: str) -> dict | None:
        row = self.db.one(
            "SELECT b.* FROM bloodline_members bm JOIN bloodlines b ON b.bloodline_id = bm.bloodline_id WHERE bm.character_id = ? ORDER BY b.name LIMIT 1",
            (character_id,),
        )
        return dict(row) if row else None

    def record_population_change(self, species_name: str, delta: int, world_id: str | None = None) -> dict:
        species = self.db.one("SELECT * FROM species WHERE name = ?", (species_name,))
        if species is None:
            species = self.create_species(species_name)
        new_population = max(0, int(species["population"]) + int(delta))
        self.db.execute("UPDATE species SET population = ? WHERE species_id = ?", (new_population, species["species_id"]))
        if world_id:
            self.db.execute("INSERT INTO species_populations (population_id, species_id, world_id, population, habitat, migration_state, updated_year) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(species_id, world_id) DO UPDATE SET population = excluded.population, updated_year = excluded.updated_year", (str(uuid.uuid4()), species["species_id"], world_id, new_population, "unknown", "stable", self.date(world_id).year))
        return {"name": species["name"], "population": new_population}

    def create_bloodline(self, name: str, species_name: str, affinity: str = "balanced", expression_state: str = "dormant", notes: str = "") -> dict:
        species = self.db.one("SELECT * FROM species WHERE name = ?", (species_name,))
        if species is None:
            species = self.create_species(species_name)
        existing = self.db.one("SELECT * FROM bloodlines WHERE name = ?", (name,))
        if existing:
            return dict(existing)
        bloodline_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO bloodlines (bloodline_id, name, species_id, affinity, expression_state, strength, notes) VALUES (?, ?, ?, ?, ?, ?, ?)", (bloodline_id, name, species["species_id"], affinity, expression_state, 1 if expression_state == "dormant" else 3, notes))
        return dict(self.db.one("SELECT * FROM bloodlines WHERE bloodline_id = ?", (bloodline_id,)))

    def assign_bloodline(self, character_id: str, bloodline_id: str, expression: str = "dormant") -> dict:
        self.db.execute("INSERT INTO bloodline_members (bloodline_id, character_id, expression, awakened, strength) VALUES (?, ?, ?, ?, ?) ON CONFLICT(bloodline_id, character_id) DO UPDATE SET expression = excluded.expression, awakened = excluded.awakened, strength = excluded.strength", (bloodline_id, character_id, expression, 1 if expression in {"strong", "dominant", "awakened", "transcendent"} else 0, 1 if expression == "dormant" else 3))
        return dict(self.db.one("SELECT * FROM bloodline_members WHERE bloodline_id = ? AND character_id = ?", (bloodline_id, character_id)))

    def mutate_character(self, character_id: str, mutation_name: str, mutation_type: str = "beneficial", severity: int = 1) -> dict:
        character = self.character(character_id)
        species = self.species_for_character(character_id)
        mutation = mutation_effect(mutation_name)
        mutation_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO mutations (mutation_id, character_id, species_id, name, mutation_type, severity, effect, discovered_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (mutation_id, character_id, species["species_id"], mutation_name, mutation_type, severity, mutation["effect"], self.date(character["world_id"]).year))
        return dict(self.db.one("SELECT * FROM mutations WHERE mutation_id = ?", (mutation_id,)))

    def inherit_traits_for_new_character(self, parent_a: dict | None, parent_b: dict | None, species_name: str = "Human", rng: random.Random | None = None) -> dict:
        return inherit_traits_for_new_character(parent_a, parent_b, species_name, rng)

    def create_character(self, world_id: str, name: str, age: int = 18, species: str = "Human", origin: str = "Azure Village", profession: str = "Farmer", background: str = "Farmer", personality: str = "Steady") -> str:
        self.create_species(species, origin=origin)
        location = self.db.one("SELECT location_id FROM locations WHERE world_id = ? AND name = ?", (world_id, origin)) or self.db.one("SELECT location_id FROM locations WHERE world_id = ? LIMIT 1", (world_id,))
        if location is None:
            raise ValueError("World has no locations")
        character_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO characters (character_id, world_id, name, age, sex, species, origin, profession, background, personality, location_id, birth_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (character_id, world_id, name, age, "Unknown", species, origin, profession, background, personality, location["location_id"], 1 - age))
        self.record_population_change(species, 1, world_id)
        self.cultivation.ensure(character_id)
        self.db.execute("INSERT INTO inventories VALUES (?, 'Food', 5)", (character_id,))
        first_breath = self.db.one("SELECT achievement_id FROM achievements WHERE code = 'first_breath'")
        if first_breath:
            self.db.execute("INSERT INTO character_achievements VALUES (?, ?, ?)", (character_id, first_breath["achievement_id"], self.date(world_id).text()))
        family_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO families VALUES (?, ?, ?, ?)", (family_id, world_id, f"The {name} Family", self.date(world_id).year))
        self.db.execute("INSERT INTO family_members VALUES (?, ?, 'founder', ?, NULL)", (family_id, character_id, self.date(world_id).year))
        self.log(world_id, character_id, "personal", f"{name} begins an ordinary life in {origin}.", 2)
        return character_id

    def log(self, world_id: str, character_id: str | None, kind: str, text: str, importance: int = 1) -> None:
        date = self.date(world_id)
        self.db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), world_id, character_id, kind, text, date.year, date.month, date.day, importance))

    def date(self, world_id: str) -> GameDate:
        row = self.db.one("SELECT year, month, day, hour FROM worlds WHERE world_id = ?", (world_id,))
        if row is None:
            raise ValueError("Unknown world")
        return GameDate(row["year"], row["month"], row["day"], row["hour"])

    def character(self, character_id: str):
        row = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        if row is None:
            raise ValueError("Unknown character")
        return row

    def market_for_location(self, world_id: str, location_name: str) -> dict:
        return self.economy.market_for_location(world_id, location_name)

    def market_price(self, world_id: str, market_id: str, good: str) -> dict:
        return self.economy.market_price(world_id, market_id, good)

    def adjust_market_supply(self, world_id: str, market_id: str, good: str, supply_delta: int, demand_delta: int = 0) -> dict:
        return self.economy.adjust_market_supply(world_id, market_id, good, supply_delta, demand_delta)

    def buy_item(self, character_id: str, good: str, quantity: int = 1) -> dict:
        return self.economy.buy_item(character_id, good, quantity)

    def sell_item(self, character_id: str, good: str, quantity: int = 1) -> dict:
        return self.economy.sell_item(character_id, good, quantity)

    def create_bank(self, world_id: str, name: str, location: str, capital: int = 1000) -> dict:
        return self.economy.create_bank(world_id, name, location, capital)

    def issue_loan(self, borrower_id: str, bank_id: str, principal: int, interest_rate: int = 10, term_days: int = 30) -> dict:
        return self.economy.issue_loan(borrower_id, bank_id, principal, interest_rate, term_days)

    def repay_loan(self, borrower_id: str, loan_id: str, amount: int) -> dict:
        return self.economy.repay_loan(borrower_id, loan_id, amount)

    def simulate_economy(self, world_id: str, days: int = 1) -> dict:
        return self.economy.simulate(world_id, days)

    def plan_journey(self, traveler_id: str, origin: str, destination: str, transport_type: str = "walking") -> dict:
        return self.transport.plan_journey(traveler_id, origin, destination, transport_type)

    def create_route(self, world_id: str, origin: str, destination: str, distance: int, terrain: str = "road", danger: int = 0, travel_cost: int = 0) -> dict:
        return self.transport.create_route(world_id, origin, destination, distance, terrain, danger, travel_cost)

    def depart_journey(self, journey_id: str) -> dict:
        return self.transport.depart_journey(journey_id)

    def create_cargo(self, world_id: str, good: str, quantity: int, origin: str, destination: str, owner_id: str | None = None, value: int = 0) -> dict:
        return self.transport.create_cargo(world_id, good, quantity, origin, destination, owner_id, value)

    def plan_cargo_journey(self, cargo_id: str, transport_type: str = "walking") -> dict:
        return self.transport.plan_cargo_journey(cargo_id, transport_type)

    def create_warehouse(self, world_id: str, name: str, location: str, capacity: int = 100, owner_id: str | None = None) -> dict:
        return self.transport.create_warehouse(world_id, name, location, capacity, owner_id)

    def create_infrastructure(self, world_id: str, name: str, kind: str, location: str, condition: int = 100, owner_id: str | None = None) -> dict:
        return self.transport.create_infrastructure(world_id, name, kind, location, condition, owner_id)

    def maintain_infrastructure(self, infrastructure_id: str, days: int = 1) -> dict:
        return self.transport.maintain_infrastructure(infrastructure_id, days)

    def repair_infrastructure(self, infrastructure_id: str, amount: int = 10) -> dict:
        return self.transport.repair_infrastructure(infrastructure_id, amount)

    def send_message(self, sender_id: str, receiver_id: str, content: str, method: str = "courier", secrecy: str = "PRIVATE") -> dict:
        return self.transport.send_message(sender_id, receiver_id, content, method, secrecy)

    def inbox(self, receiver_id: str) -> list[dict]:
        return self.transport.inbox(receiver_id)

    def create_organization(self, world_id: str, name: str, org_type: str, owner_id: str | None = None) -> dict:
        organization_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO organizations (organization_id, world_id, owner_id, name, type) VALUES (?, ?, ?, ?, ?)", (organization_id, world_id, owner_id, name, org_type))
        return dict(self.db.one("SELECT * FROM organizations WHERE organization_id = ?", (organization_id,)))

    def organization(self, organization_id: str) -> dict:
        row = self.db.one("SELECT * FROM organizations WHERE organization_id = ?", (organization_id,))
        if row is None:
            raise ValueError("Unknown organization")
        return dict(row)

    def join_organization(self, character_id: str, organization_id: str, rank: str = "member", role: str = "member") -> dict:
        organization = self.organization(organization_id)
        year = self.date(organization["world_id"]).year
        self.db.execute("INSERT OR IGNORE INTO organization_members (organization_id, character_id, rank, role, joined_year) VALUES (?, ?, ?, ?, ?)", (organization_id, character_id, rank, role, year))
        self.db.execute("UPDATE organization_members SET rank = ?, role = ? WHERE organization_id = ? AND character_id = ?", (rank, role, organization_id, character_id))
        return dict(self.db.one("SELECT * FROM organization_members WHERE organization_id = ? AND character_id = ?", (organization_id, character_id)))

    def organization_member(self, character_id: str, organization_id: str) -> dict:
        row = self.db.one("SELECT * FROM organization_members WHERE organization_id = ? AND character_id = ?", (organization_id, character_id))
        if row is None:
            raise ValueError("Character is not a member of the organization")
        return dict(row)

    def promote_member(self, character_id: str, organization_id: str, rank: str) -> dict:
        self.db.execute("UPDATE organization_members SET rank = ? WHERE organization_id = ? AND character_id = ?", (rank, organization_id, character_id))
        return self.organization_member(character_id, organization_id)

    def assign_role(self, character_id: str, organization_id: str, role: str, permissions: str = "basic") -> dict:
        self.db.execute("UPDATE organization_members SET role = ?, permissions = ? WHERE organization_id = ? AND character_id = ?", (role, permissions, organization_id, character_id))
        return self.organization_member(character_id, organization_id)

    def can_perform(self, character_id: str, organization_id: str, action_name: str) -> bool:
        membership = self.organization_member(character_id, organization_id)
        permissions = (membership.get("permissions") or "basic").lower().replace(",", " ").split()
        return "all" in permissions or action_name.lower() in permissions or "write" in permissions or "treasurer" in (membership.get("role") or "").lower()

    def set_leader(self, organization_id: str, character_id: str) -> dict:
        self.db.execute("UPDATE organizations SET owner_id = ?, leader_id = ? WHERE organization_id = ?", (character_id, character_id, organization_id))
        return self.organization(organization_id)

    def set_succession(self, organization_id: str, heir_id: str, method: str = "heir") -> dict:
        self.db.execute("UPDATE organizations SET succession_rules = ? WHERE organization_id = ?", (method, organization_id))
        self.db.execute("INSERT INTO organization_succession (succession_id, organization_id, heir_id, method) VALUES (?, ?, ?, ?)", (str(uuid.uuid4()), organization_id, heir_id, method))
        return dict(self.db.one("SELECT * FROM organization_succession WHERE organization_id = ? ORDER BY rowid DESC LIMIT 1", (organization_id,)))

    def record_organization_event(self, organization_id: str, kind: str, text: str) -> dict:
        date = self.date(self.organization(organization_id)["world_id"])
        event_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO organization_events (event_id, organization_id, kind, text, year, month, day) VALUES (?, ?, ?, ?, ?, ?, ?)", (event_id, organization_id, kind, text, date.year, date.month, date.day))
        return dict(self.db.one("SELECT * FROM organization_events WHERE event_id = ?", (event_id,)))

    def organization_events(self, organization_id: str) -> list:
        return self.db.all("SELECT * FROM organization_events WHERE organization_id = ? ORDER BY rowid DESC", (organization_id,))

    def create_military_unit(self, world_id: str, name: str, unit_type: str = "infantry", commander_id: str | None = None, organization_id: str | None = None) -> dict:
        unit_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO military_units (unit_id, world_id, name, owner_id, organization_id, commander_id) VALUES (?, ?, ?, ?, ?, ?)", (unit_id, world_id, name, commander_id, organization_id, commander_id))
        return dict(self.db.one("SELECT * FROM military_units WHERE unit_id = ?", (unit_id,)))

    def recruit_character_to_unit(self, character_id: str, unit_id: str, role: str = "soldier") -> dict:
        unit = self.db.one("SELECT * FROM military_units WHERE unit_id = ?", (unit_id,))
        if unit is None:
            raise ValueError("Unknown military unit")
        self.db.execute("INSERT OR IGNORE INTO military_unit_members (unit_id, character_id, role, rank, joined_year) VALUES (?, ?, ?, 'member', ?)", (unit_id, character_id, role, self.date(unit["world_id"]).year))
        return dict(self.db.one("SELECT * FROM military_unit_members WHERE unit_id = ? AND character_id = ?", (unit_id, character_id)))

    def create_campaign(self, world_id: str, attacker_id: str, defender_id: str, objective: str = "capture territory") -> dict:
        campaign_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO military_campaigns (campaign_id, world_id, attacker_id, defender_id, objective) VALUES (?, ?, ?, ?, ?)", (campaign_id, world_id, attacker_id, defender_id, objective))
        return dict(self.db.one("SELECT * FROM military_campaigns WHERE campaign_id = ?", (campaign_id,)))

    def create_battle(self, world_id: str, location: str, campaign_id: str | None = None, objective: str = "attack") -> dict:
        battle_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO military_battles (battle_id, world_id, campaign_id, location, objective) VALUES (?, ?, ?, ?, ?)", (battle_id, world_id, campaign_id, location, objective))
        return dict(self.db.one("SELECT * FROM military_battles WHERE battle_id = ?", (battle_id,)))

    def create_supply_route(self, world_id: str, name: str, source: str, destination: str, status: str = "active") -> dict:
        route_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO military_supply_routes (route_id, world_id, name, source, destination, status) VALUES (?, ?, ?, ?, ?, ?)", (route_id, world_id, name, source, destination, status))
        return dict(self.db.one("SELECT * FROM military_supply_routes WHERE route_id = ?", (route_id,)))

    def execute_military_order(self, character_id: str, unit_id: str, command: str) -> str:
        unit = self.db.one("SELECT * FROM military_units WHERE unit_id = ?", (unit_id,))
        if unit is None or unit["commander_id"] != character_id:
            return "You do not command this unit."
        self.db.execute("INSERT INTO military_orders (order_id, world_id, unit_id, character_id, command) VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), unit["world_id"], unit_id, character_id, command))
        return f"The unit was ordered to {command}."

    def perform(self, character_id: str, action: Action | str) -> str:
        action = parse_command(action) if isinstance(action, str) else action
        character = self.character(character_id)
        if not character["alive"]:
            return "This life has ended. Create another character to continue in this world."
        world_id = character["world_id"]
        if action.verb == "help":
            return "Try: look, status, inventory, work for 5 days, cultivate for 30 days, travel to Eastern Market, talk, rest, or save."
        if action.verb == "status":
            return f"{character['name']}, age {character['age']} | {realm_name(character['cultivation'])} | Health {character['health']} | Qi {character['qi']} | Soul {character['soul']} | Wealth {character['wealth']}"
        if action.verb == "inventory":
            items = self.db.all("SELECT item, quantity FROM inventories WHERE character_id = ? AND quantity > 0", (character_id,))
            return "Inventory: " + (", ".join(f"{item['item']} x{item['quantity']}" for item in items) or "empty")
        if action.verb == "join":
            if "army" in action.target:
                unit = self.db.one("SELECT * FROM military_units WHERE world_id = ? ORDER BY rowid DESC LIMIT 1", (world_id,))
                if unit is None:
                    unit = self.create_military_unit(world_id, "Village Guard", commander_id=character_id)
                self.recruit_character_to_unit(character_id, unit["unit_id"])
                return f"{character['name']} joined the army."
            organization = self.db.one("SELECT * FROM organizations WHERE world_id = ? AND name LIKE ? LIMIT 1", (world_id, f"%{action.target}%"))
            if organization is None:
                return f"No organization named {action.target} is known here."
            self.join_organization(character_id, organization["organization_id"], "Member", "Member")
            return f"{character['name']} joined {organization['name']}."
        if action.verb == "leave":
            organization = self.db.one("SELECT * FROM organizations WHERE world_id = ? AND name LIKE ? LIMIT 1", (world_id, f"%{action.target}%"))
            if organization is None:
                return f"No organization named {action.target} is known here."
            self.db.execute("UPDATE organization_members SET status = 'left' WHERE organization_id = ? AND character_id = ?", (organization["organization_id"], character_id))
            return f"{character['name']} left {organization['name']}."
        if action.verb == "balance":
            return f"{character['name']} has {character['wealth']} coins available."
        if action.verb == "market":
            location = self.db.one("SELECT name FROM locations WHERE location_id = ?", (character["location_id"],))
            market = self.market_for_location(world_id, location["name"] if location else "local market")
            if action.target:
                price = self.market_price(world_id, market["market_id"], action.target)
                return f"{price['good'].title()} costs {price['unit_price']} coins here; supply {price['supply']}, demand {price['demand']}."
            prices = self.db.all("SELECT good, unit_price FROM market_prices WHERE market_id = ? ORDER BY good", (market["market_id"],))
            return market["name"] + ": " + ", ".join(f"{row['good']} {row['unit_price']} coins" for row in prices)
        if action.verb == "routes":
            routes = self.db.all("SELECT from_location, to_location, distance, travel_cost, danger FROM routes WHERE world_id = ? ORDER BY distance", (world_id,))
            return "Routes: " + ", ".join(f"{row['from_location']} to {row['to_location']} ({row['distance']} days, {row['travel_cost']} coins)" for row in routes)
        if action.verb == "inbox":
            messages = self.inbox(character_id)
            return "Inbox: " + ("; ".join(message["content"] for message in messages) or "No delivered messages.")
        if action.verb == "look":
            location = self.db.one("SELECT * FROM locations WHERE location_id = ?", (character["location_id"],))
            return location["description"] if location else "You see an unfamiliar road."
        hours = {"farm": max(1, action.duration) * 24, "cultivate": max(1, action.duration) * 24, "rest": max(1, action.duration) * 8, "travel": max(1, action.duration) * 72, "talk": 2}.get(action.verb, 1)
        travel_note = ""
        if action.verb == "farm":
            self.db.execute("UPDATE characters SET wealth = wealth + ?, hunger = MAX(0, hunger - 3), fatigue = MIN(100, fatigue + 8) WHERE character_id = ?", (max(1, action.duration * 2), character_id))
        elif action.verb == "cultivate":
            cultivation_result = self.cultivation.cultivate(character_id, "meditation", max(1, action.duration))
            self.db.execute("UPDATE characters SET qi = MIN(100, qi + ?), foundation = MIN(100, foundation + 1), fatigue = MIN(100, fatigue + 3) WHERE character_id = ?", (max(1, action.duration // 5), character_id))
            message = cultivation_result.text
        elif action.verb == "rest":
            self.db.execute("UPDATE characters SET fatigue = MAX(0, fatigue - 25), health = MIN(100, health + 5), morale = MIN(100, morale + 3) WHERE character_id = ?", (character_id,))
        elif action.verb == "travel" and action.target:
            origin = self.db.one("SELECT name FROM locations WHERE location_id = ?", (character["location_id"],))
            destination = self.db.one("SELECT * FROM locations WHERE world_id = ? AND name LIKE ?", (world_id, f"%{action.target}%"))
            route = self.db.one("SELECT * FROM routes WHERE world_id = ? AND ((from_location = ? AND to_location = ?) OR (from_location = ? AND to_location = ?))", (world_id, origin["name"], destination["name"] if destination else "", destination["name"] if destination else "", origin["name"])) if origin and destination else None
            if destination is None or route is None:
                return "You do not know a safe route there."
            if character["wealth"] < route["travel_cost"]:
                return f"The journey costs {route['travel_cost']} coins, but you only have {character['wealth']}."
            journey = self.plan_journey(character_id, origin["name"], destination["name"], "walking")
            self.depart_journey(journey["journey_id"])
            self.db.execute("UPDATE characters SET wealth = wealth - ?, fatigue = MIN(100, fatigue + ?) WHERE character_id = ?", (route["travel_cost"], route["distance"] * 4, character_id))
            hours = journey["estimated_hours"]
            rng = random.Random(self.seed + self.date(world_id).day_of_year + int(character_id.replace("-", "")[:8], 16))
            if rng.randint(1, 100) <= route["danger"] * 5:
                travel_note = " On the road, you notice signs of danger and arrive more cautiously than planned."
                self.db.execute("UPDATE characters SET morale = MAX(0, morale - 3) WHERE character_id = ?", (character_id,))
                self.log(world_id, character_id, "travel", f"A dangerous sign delayed the journey to {destination['name']}.", 2)
        elif action.verb == "talk":
            message = self.talk(character_id, action.target)
        elif action.verb in {"buy", "sell"}:
            message = self.trade(character_id, action.verb, action.target)
        date = self.tick.advance(world_id, hours)
        if action.verb != "talk":
            if action.verb not in {"buy", "sell", "cultivate"}:
                message = action_message(action.verb, date) + travel_note
        self.log(world_id, character_id, "personal", message)
        self.situations.refresh(character_id)
        return message

    def trade(self, character_id: str, verb: str, item: str) -> str:
        try:
            result = self.buy_item(character_id, item) if verb == "buy" else self.sell_item(character_id, item)
        except ValueError as error:
            return str(error)
        action = "buy" if verb == "buy" else "sell"
        return f"You {action} one {result['good']} for {result['unit_price']} coins."

    def talk(self, character_id: str, target: str = "") -> str:
        character = self.character(character_id)
        pattern = f"%{target}%" if target else "%"
        npc = self.db.one("SELECT * FROM npcs WHERE world_id = ? AND location_id = ? AND alive = 1 AND (name LIKE ? OR profession LIKE ?) ORDER BY name LIMIT 1", (character["world_id"], character["location_id"], pattern, pattern))
        if npc is None:
            return "No one nearby seems ready to talk."
        response = self.converse(character_id, npc["npc_id"], "Hello. How are you today?")
        self.db.execute("UPDATE relationships SET familiarity = MIN(100, familiarity + 4), trust = MIN(100, trust + 1) WHERE source_id = ? AND target_id = ?", (character_id, npc["npc_id"]))
        return response

    def converse(self, character_id: str, npc_id: str, message: str) -> str:
        return self.conversations.converse(character_id, npc_id, message)

    def set_ai_provider(self, provider: AIProvider) -> None:
        self.provider = provider
        self.conversations.provider = provider
        self.conversations.brain.provider = provider

    def nearby_npcs(self, character_id: str) -> list:
        character = self.character(character_id)
        return self.db.all("SELECT npc_id, name, profession, age, realm, alive FROM npcs WHERE world_id = ? AND location_id = ? AND alive = 1 ORDER BY name", (character["world_id"], character["location_id"]))

    def conversation_history(self, character_id: str, npc_id: str, limit: int = 12) -> list:
        return self.conversations.history(character_id, npc_id, limit)

    def relationships(self, character_id: str) -> list:
        return self.db.all("SELECT r.*, n.name, n.profession, n.alive FROM relationships r JOIN npcs n ON n.npc_id = r.target_id WHERE r.source_id = ? ORDER BY r.familiarity DESC", (character_id,))

    def family(self, character_id: str):
        return self.db.one("SELECT f.* FROM families f JOIN family_members m ON m.family_id = f.family_id WHERE m.character_id = ?", (character_id,))

    def journal(self, character_id: str) -> dict[str, list]:
        character = self.character(character_id)
        return {
            "events": self.db.all("SELECT text, year, month, day FROM events WHERE character_id = ? ORDER BY rowid DESC LIMIT 20", (character_id,)),
            "memories": self.db.all("SELECT text, importance FROM memories WHERE owner_id = ? ORDER BY importance DESC, rowid DESC LIMIT 12", (character_id,)),
            "situations": self.open_situations(character_id),
            "relationships": self.relationships(character_id),
            "goals": [character["short_goal"], character["ambition"]],
        }

    def map_text(self, world_id: str, current_location_id: str) -> str:
        locations = {row["name"]: row["location_id"] for row in self.db.all("SELECT name, location_id FROM locations WHERE world_id = ?", (world_id,))}
        current = next((name for name, location_id in locations.items() if location_id == current_location_id), "Unknown")
        lines = ["World map", "", f"                 Cloudstep Sect", "                       |", "Whispering Forest -- Azure Village -- Eastern Market", "                       |", "                 Old Road", "", f"You are here: {current}"]
        return "\n".join(lines)

    def open_situations(self, character_id: str) -> list:
        self.situations.refresh(character_id)
        return self.situations.list_open(character_id)

    def resolve_situation(self, character_id: str, situation_id: str, choice: str) -> str:
        result = self.situations.resolve(character_id, situation_id, choice)
        character = self.character(character_id)
        self.log(character["world_id"], character_id, "situation", result, 2)
        return result

    def attempt_breakthrough(self, character_id: str) -> str:
        character = self.character(character_id)
        result, text, chance = self.cultivation.breakthrough(character_id)
        if result:
            self.db.execute("UPDATE characters SET cultivation = MIN(49, cultivation + 1), qi = 20, foundation = MIN(100, foundation + 5) WHERE character_id = ?", (character_id,))
        self.log(character["world_id"], character_id, "cultivation", text, 3)
        return text

    def cultivation_state(self, character_id: str):
        return self.cultivation.state(character_id)

    def study_dao(self, character_id: str, dao_name: str = "Sword") -> str:
        return self.cultivation.study_dao(character_id, dao_name)

    def practice_technique(self, character_id: str, technique_name: str = "Breath of Still Water") -> str:
        return self.cultivation.practice_technique(character_id, technique_name)

    def generate_tribulation(self, character_id: str) -> dict:
        return self.tribulations.generate(character_id)

    def tribulation_warning(self, character_id: str) -> str:
        return self.tribulations.warning(character_id)

    def resolve_tribulation(self, character_id: str, action: str = "defend") -> str:
        return self.tribulations.resolve(character_id, action)

    def start_combat(self, character_id: str, npc_id: str) -> Combat:
        character = self.character(character_id)
        npc = self.db.one("SELECT * FROM npcs WHERE npc_id = ? AND alive = 1", (npc_id,))
        if npc is None or npc["world_id"] != character["world_id"] or npc["location_id"] != character["location_id"]:
            raise ValueError("That opponent is not available here")
        state = self.cultivation_state(character_id)
        player_power = realm_power(state["realm_id"], state["internal_level"]) + state["body_strength"] + state["dao_intent"]
        enemy_power = realm_power(npc["realm"]) + npc["qi"] // 2
        combat = Combat(Combatant(character["name"], character["health"], character["qi"], player_power, soul=state["soul_strength"], perception=state["perception"]), Combatant(npc["name"], npc["health"], npc["qi"], enemy_power, soul=npc["soul"], perception=30), self.seed, terrain="village", weather=self.date(character["world_id"]).weather(self.seed), distance=6)
        self.active_combats[character_id] = combat
        return combat

    def combat_action(self, character_id: str, action: str) -> str:
        combat = self.active_combats.get(character_id)
        if combat is None:
            return "You are not currently in combat."
        result = combat.act(action)
        character = self.character(character_id)
        self.db.execute("UPDATE characters SET health = ?, qi = ? WHERE character_id = ?", (combat.player.health, combat.player.qi, character_id))
        if combat.finished:
            if combat.player.health <= 0:
                self.kill_character(character_id, f"combat with {combat.enemy.name}")
                outcome = "death"
            elif combat.enemy.health <= 0:
                npc = self.db.one("SELECT npc_id FROM npcs WHERE name = ? AND world_id = ?", (combat.enemy.name, character["world_id"]))
                if npc:
                    self.db.execute("UPDATE npcs SET alive = 0, health = 0 WHERE npc_id = ?", (npc["npc_id"],))
                outcome = "victory"
            else:
                outcome = "escape"
            date = self.date(character["world_id"])
            self.db.execute("INSERT INTO combat_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), character["world_id"], character["location_id"], f"{character_id},{combat.enemy.name}", outcome, combat.round, result, date.day_of_year))
            del self.active_combats[character_id]
        return result

    def kill_character(self, character_id: str, cause: str = "an unknown danger") -> None:
        character = self.character(character_id)
        if character["alive"]:
            date = self.date(character["world_id"])
            self.db.execute("UPDATE characters SET alive = 0, health = 0, death_date = ?, death_cause = ? WHERE character_id = ?", (date.text(), cause, character_id))
            self.log(character["world_id"], character_id, "death", f"{character['name']} died by {cause}.", 5)

    def save(self, world_id: str, character_id: str | None, name: str = "Autosave") -> str:
        save_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO save_games VALUES (?, ?, ?, ?, datetime('now'))", (save_id, world_id, character_id, name))
        return save_id

    def latest_save(self) -> tuple[str, str | None] | None:
        row = self.db.one("SELECT world_id, character_id FROM save_games ORDER BY created_at DESC, rowid DESC LIMIT 1")
        return (row["world_id"], row["character_id"]) if row else None

    def legacy(self, world_id: str) -> list[str]:
        rows = self.db.all("SELECT text FROM events WHERE world_id = ? AND kind IN ('death', 'personal') ORDER BY rowid DESC LIMIT 10", (world_id,))
        return [row["text"] for row in rows]
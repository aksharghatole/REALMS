import random
import uuid
from pathlib import Path

from game.actions import Action, parse_command
from game.clock import GameDate
from game.cultivation.realms import breakthrough, realm_name
from game.cultivation.system import CultivationEngine
from game.cultivation.tribulations import TribulationEngine
from game.database.db import Database
from game.narrative import action_message
from game.simulation.world_tick import WorldTick
from game.simulation.world_simulation import WorldSimulation
from game.simulation.situations import SituationEngine
from game.world.generator import WorldGenerator
from game.achievements import INITIAL_ACHIEVEMENTS
from game.ai.conversation import ConversationService
from game.ai.provider import AIProvider, configured_provider
from game.combat.combat import Combat, Combatant
from game.cultivation.realms import realm_power


class GameEngine:
    """Authoritative application service for worlds, characters, and actions."""

    def __init__(self, database: Database, seed: int = 184729, provider: AIProvider | None = None):
        self.db = database
        self.seed = seed
        self.tick = WorldTick(database, seed)
        self.simulation = WorldSimulation(database, seed)
        self.situations = SituationEngine(database, seed)
        self.provider = provider or configured_provider()
        self.conversations = ConversationService(database, seed, self.provider)
        self.cultivation = CultivationEngine(database, seed)
        self.tribulations = TribulationEngine(database, seed)
        self.active_combats: dict[str, Combat] = {}

    @classmethod
    def open(cls, path: str | Path, seed: int = 184729) -> "GameEngine":
        return cls(Database(path), seed)

    @staticmethod
    def _coerce_id(value: str | dict | tuple | None, key: str = "character_id") -> str | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(key)
        if isinstance(value, tuple):
            return value[0] if value else None
        return str(value)

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

    def create_character(self, world_id: str, name: str, age: int = 18, species: str = "Human", origin: str = "Azure Village", profession: str = "Farmer", background: str = "Farmer", personality: str = "Steady") -> str:
        location = self.db.one("SELECT location_id FROM locations WHERE world_id = ? AND name = ?", (world_id, origin)) or self.db.one("SELECT location_id FROM locations WHERE world_id = ? LIMIT 1", (world_id,))
        if location is None:
            raise ValueError("World has no locations")
        character_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO characters (character_id, world_id, name, age, sex, species, origin, profession, background, personality, location_id, birth_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (character_id, world_id, name, age, "Unknown", species, origin, profession, background, personality, location["location_id"], 1 - age))
        self.cultivation.ensure(character_id)
        self.db.execute("INSERT INTO inventories VALUES (?, 'Food', 5)", (character_id,))
        first_breath = self.db.one("SELECT achievement_id FROM achievements WHERE code = 'first_breath'")
        if first_breath:
            self.db.execute("INSERT INTO character_achievements VALUES (?, ?, ?)", (character_id, first_breath["achievement_id"], self.date(world_id).text()))
        family_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO families VALUES (?, ?, ?, ?)", (family_id, world_id, f"The {name} Family", self.date(world_id).year))
        self.db.execute("INSERT INTO family_members VALUES (?, ?, 'founder', ?, NULL)", (family_id, character_id, self.date(world_id).year))
        self.db.execute("UPDATE characters SET family_id = ? WHERE character_id = ?", (family_id, character_id))
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

    def world_state(self, world_id: str) -> dict:
        return self.simulation.ensure_world_state(world_id)

    def ensure_planet(self, world_id: str, name: str) -> dict:
        return self.simulation.ensure_planet(world_id, name)

    def create_war(self, world_id: str, attacker: str, defender: str, cause: str) -> dict:
        return self.simulation.create_war(world_id, attacker, defender, cause)

    def simulate_world(self, world_id: str, days: int = 30) -> bool:
        return self.simulation.simulate(world_id, days)

    def civilization_state(self, world_id: str) -> dict:
        row = self.db.one("SELECT * FROM civilization_states WHERE world_id = ?", (world_id,))
        if row is not None:
            return dict(row)
        world = self.db.one("SELECT name FROM worlds WHERE world_id = ?", (world_id,))
        state_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO civilization_states (civilization_id, world_id, name, technology_level, industrial_capacity, infrastructure_quality, education, literacy, scientific_knowledge, production_capacity, urbanization, energy_capacity, resource_security, stability) VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 50)",
            (state_id, world_id, world["name"] if world else "Azure Kingdom"),
        )
        return self.civilization_state(world_id)

    def register_technology(self, world_id: str, name: str, domain: str = "general", phase: str = "Primitive", description: str = "", prerequisites: str = "", inventor: str = "", civilization: str = "Azure Kingdom") -> dict:
        existing = self.db.one("SELECT * FROM technologies WHERE world_id = ? AND name = ?", (world_id, name))
        if existing:
            return dict(existing)
        technology_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO technologies (technology_id, world_id, name, domain, phase, description, prerequisites, inventor, discovery_year, status, adoption, complexity, reliability, civilization) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'known', 1, 1, 1, ?)",
            (technology_id, world_id, name, domain, phase, description, prerequisites, inventor or "Unknown Innovator", self.date(world_id).year, civilization),
        )
        return self.db.one("SELECT * FROM technologies WHERE technology_id = ?", (technology_id,))

    def start_research_project(self, world_id: str, lead_character_id: str | dict, technology_name: str, institution: str = "Village Workshop", domain: str = "general", funding: int = 25) -> dict:
        lead_character_id = self._coerce_id(lead_character_id, "character_id")
        existing = self.db.one("SELECT * FROM research_projects WHERE world_id = ? AND technology_name = ? AND status = 'active' LIMIT 1", (world_id, technology_name))
        if existing:
            return dict(existing)
        project_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO research_projects (project_id, world_id, lead_character_id, institution, technology_name, domain, progress, funding, status, started_year, started_month, started_day) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'active', ?, ?, ?)",
            (project_id, world_id, lead_character_id, institution, technology_name, domain, funding, self.date(world_id).year, self.date(world_id).month, self.date(world_id).day),
        )
        return self.db.one("SELECT * FROM research_projects WHERE project_id = ?", (project_id,))

    def advance_civilization(self, world_id: str, days: int = 1) -> dict:
        state = self.civilization_state(world_id)
        active_projects = self.db.all("SELECT * FROM research_projects WHERE world_id = ? AND status = 'active' ORDER BY started_year ASC", (world_id,))
        growth = 1 + min(len(active_projects), 5)
        for project in active_projects:
            boost = 15 + (state["scientific_knowledge"] // 4)
            new_progress = project["progress"] + boost
            self.db.execute("UPDATE research_projects SET progress = ?, funding = funding + 5 WHERE project_id = ?", (new_progress, project["project_id"]))
            if new_progress >= 100:
                self.register_technology(world_id, project["technology_name"], project["domain"], "Industrial", description=f"Developed through {project['institution']} research.", civilization=state["name"])
                self.db.execute("UPDATE research_projects SET status = 'completed', progress = 100 WHERE project_id = ?", (project["project_id"],))
                self.db.execute(
                    "UPDATE civilization_states SET technology_level = technology_level + 1, scientific_knowledge = scientific_knowledge + 10, industrial_capacity = industrial_capacity + 6, infrastructure_quality = infrastructure_quality + 3, production_capacity = production_capacity + 5, education = education + 2, literacy = literacy + 2 WHERE world_id = ?",
                    (world_id,),
                )
        if not active_projects:
            self.db.execute(
                "UPDATE civilization_states SET technology_level = technology_level + ?, industrial_capacity = industrial_capacity + ?, infrastructure_quality = infrastructure_quality + ?, scientific_knowledge = scientific_knowledge + ? WHERE world_id = ?",
                (growth, max(1, growth // 2), max(1, growth // 3), max(1, growth // 2), world_id),
            )
        else:
            self.db.execute(
                "UPDATE civilization_states SET technology_level = technology_level + ?, industrial_capacity = industrial_capacity + ?, infrastructure_quality = infrastructure_quality + ?, scientific_knowledge = scientific_knowledge + ? WHERE world_id = ?",
                (growth, max(1, growth // 2), max(1, growth // 3), max(1, growth // 2), world_id),
            )
        return self.civilization_state(world_id)

    def create_company(self, world_id: str, founder_id: str | dict, name: str, industry: str = "Manufacturing") -> dict:
        founder_id = self._coerce_id(founder_id, "character_id")
        if not self.db.one("SELECT * FROM companies WHERE world_id = ? AND name = ? LIMIT 1", (world_id, name)):
            company_id = str(uuid.uuid4())
            self.db.execute(
                "INSERT INTO companies (company_id, world_id, founder_id, name, industry, status, revenue, employees, capital) VALUES (?, ?, ?, ?, ?, 'active', 0, 1, 0)",
                (company_id, world_id, founder_id, name, industry),
            )
            return self.db.one("SELECT * FROM companies WHERE company_id = ?", (company_id,))
        return self.db.one("SELECT * FROM companies WHERE world_id = ? AND name = ? LIMIT 1", (world_id, name))

    def build_infrastructure(self, world_id: str, name: str, kind: str = "road", location: str = "Azure Village", owner_id: str | dict | None = None) -> dict:
        owner_id = self._coerce_id(owner_id, "character_id")
        infrastructure_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO infrastructure (infrastructure_id, world_id, name, kind, location, owner_id, condition, status, maintenance_cost, capacity) VALUES (?, ?, ?, ?, ?, ?, 100, 'active', 0, 10)",
            (infrastructure_id, world_id, name, kind, location, owner_id),
        )
        self.db.execute("UPDATE civilization_states SET infrastructure_quality = infrastructure_quality + 1 WHERE world_id = ?", (world_id,))
        return self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,))

    def world_news(self, world_id: str) -> list[str]:
        return self.simulation.world_news(world_id)

    def character(self, character_id: str):
        row = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        if row is None:
            raise ValueError("Unknown character")
        return row

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
            self.db.execute("UPDATE characters SET location_id = ?, wealth = wealth - ?, fatigue = MIN(100, fatigue + ?) WHERE character_id = ?", (destination["location_id"], route["travel_cost"], route["distance"] * 4, character_id))
            hours = route["distance"] * 24
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
        prices = {"rice": (3, "Food"), "food": (3, "Food"), "herbs": (5, "Herbs"), "wood": (2, "Wood"), "iron": (8, "Iron")}
        price, canonical = next(((value, name) for name, (value, item_name) in prices.items() if name in item or item_name.lower() in item), (0, ""))
        character = self.character(character_id)
        if not canonical:
            return "The market does not recognize that item."
        if verb == "buy":
            if character["wealth"] < price:
                return f"You need {price} coins to buy {canonical.lower()}."
            self.db.execute("UPDATE characters SET wealth = wealth - ? WHERE character_id = ?", (price, character_id))
            self.db.execute("INSERT INTO inventories (character_id, item, quantity) VALUES (?, ?, 1) ON CONFLICT(character_id, item) DO UPDATE SET quantity = quantity + 1", (character_id, canonical))
            return f"You buy one {canonical.lower()} for {price} coins."
        held = self.db.one("SELECT quantity FROM inventories WHERE character_id = ? AND item = ?", (character_id, canonical))
        if held is None or held["quantity"] < 1:
            return f"You have no {canonical.lower()} to sell."
        self.db.execute("UPDATE inventories SET quantity = quantity - 1 WHERE character_id = ? AND item = ?", (character_id, canonical))
        self.db.execute("UPDATE characters SET wealth = wealth + ? WHERE character_id = ?", (price, character_id))
        return f"You sell one {canonical.lower()} for {price} coins."

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

    def create_exploration_site(self, world_id: str, name: str, site_type: str = "Ruins", region: str = "wilds") -> dict:
        site_id = str(uuid.uuid4())
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        seed = (world["seed"] + sum(ord(ch) for ch in name)) % 100000
        description = f"A {site_type.lower()} hidden in the {region} with an uneasy stillness." 
        self.db.execute(
            "INSERT INTO exploration_sites (site_id, world_id, name, type, region, coordinates, discovered, danger, environment, seed, state, status, description, resources, inhabitants, history, entrances) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'latent', 'unknown', ?, ?, ?, ?, 'main')",
            (site_id, world_id, name, site_type, region, f"{seed % 37},{(seed * 11) % 41}", max(1, (seed % 8) + 1), "wild", seed, description, "herbs, stone, ruins", "scouts, bandits, spirits", "old roads and buried relics"),
        )
        for resource_name in ["herbs", "ore", "stone", "crystals"]:
            resource_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO site_resources (resource_id, world_id, site_id, name, quantity, region, respawn, discovered) VALUES (?, ?, ?, ?, ?, ?, ?, 0)", (resource_id, world_id, site_id, resource_name, max(1, seed % 9 + 1), region, 30))
        return self.db.one("SELECT * FROM exploration_sites WHERE site_id = ?", (site_id,))

    def discover_site(self, character_id: str, site_id: str, discovery_mode: str = "travel") -> dict:
        character = self.character(character_id)
        site = self.db.one("SELECT * FROM exploration_sites WHERE site_id = ?", (site_id,))
        if site is None:
            raise ValueError("Unknown exploration site")
        quality_map = {"rumor": "RUMORED", "travel": "LOCATED", "search": "PARTIALLY EXPLORED", "study": "FULLY EXPLORED"}
        quality = quality_map.get(discovery_mode.lower(), "LOCATED")
        self.db.execute("UPDATE exploration_sites SET discovered = 1, state = 'active', status = ? WHERE site_id = ?", (quality, site_id))
        self.db.execute("INSERT INTO site_discoveries (discovery_id, world_id, site_id, character_id, discovered_quality, discovered_year, discovered_month, discovered_day, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), character["world_id"], site_id, character_id, quality, self.date(character["world_id"]).year, self.date(character["world_id"]).month, self.date(character["world_id"]).day, f"{character['name']} locates {site['name']} via {discovery_mode}."))
        self.log(character["world_id"], character_id, "exploration", f"{character['name']} discovers {site['name']} and marks the area as {quality.lower()}.", 3)
        return self.db.one("SELECT * FROM site_discoveries WHERE site_id = ? AND character_id = ? ORDER BY discovered_day DESC LIMIT 1", (site_id, character_id))

    def gather_resources(self, character_id: str, site_id: str, resource_name: str = "herbs") -> dict:
        character = self.character(character_id)
        resource = self.db.one("SELECT * FROM site_resources WHERE site_id = ? AND name = ?", (site_id, resource_name))
        if resource is None:
            raise ValueError("That resource is not present in this location")
        quantity = max(1, min(5, resource["quantity"]))
        self.db.execute("UPDATE site_resources SET quantity = MAX(0, quantity - ?), discovered = 1 WHERE resource_id = ?", (quantity, resource["resource_id"]))
        self.db.execute("INSERT INTO inventories (character_id, item, quantity) VALUES (?, ?, ?) ON CONFLICT(character_id, item) DO UPDATE SET quantity = quantity + excluded.quantity", (character_id, resource_name, quantity))
        self.log(character["world_id"], character_id, "exploration", f"{character['name']} gathers {quantity} {resource_name} from {self.db.one('SELECT name FROM exploration_sites WHERE site_id = ?', (site_id,))[0]}.", 2)
        return {"name": resource_name, "quantity": quantity, "site_id": site_id}

    def create_artifact(self, site_id: str, name: str, artifact_type: str = "artifact", quality: str = "Uncommon") -> dict:
        site = self.db.one("SELECT * FROM exploration_sites WHERE site_id = ?", (site_id,))
        if site is None:
            raise ValueError("Unknown site")
        artifact_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO artifacts (artifact_id, owner_id, name, artifact_type, quality, durability, effects, history) VALUES (?, NULL, ?, ?, ?, 100, 'unknown effect', ?)", (artifact_id, name, artifact_type, quality, f"Recovered from {site['name']} during a discovery."))
        return self.db.one("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))

    def create_expedition(self, world_id: str, name: str, leader_id: str, destination_site: str) -> dict:
        expedition_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO expeditions (expedition_id, world_id, name, leader_id, destination_site, status, members, supplies) VALUES (?, ?, ?, ?, ?, 'planned', ?, 'food, medicine')", (expedition_id, world_id, name, leader_id, destination_site, leader_id))
        return self.db.one("SELECT * FROM expeditions WHERE expedition_id = ?", (expedition_id,))

    def travel_route(self, world_id: str, from_location: str, to_location: str, risk: int = 1, duration: int = 1, terrain: str = "road") -> dict:
        route_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO travel_routes (route_id, world_id, from_location, to_location, risk, duration, terrain) VALUES (?, ?, ?, ?, ?, ?, ?)", (route_id, world_id, from_location, to_location, risk, duration, terrain))
        return self.db.one("SELECT * FROM travel_routes WHERE route_id = ?", (route_id,))

    def assign_artifact_owner(self, artifact_id: str, owner_id: str | None) -> dict:
        self.db.execute("UPDATE artifacts SET owner_id = ? WHERE artifact_id = ?", (owner_id, artifact_id))
        return self.db.one("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))

    def exploration_notes(self, character_id: str) -> list[str]:
        rows = self.db.all("SELECT summary FROM exploration_events WHERE character_id = ? ORDER BY rowid DESC LIMIT 8", (character_id,))
        return [row["summary"] for row in rows]

    def assign_profession(self, character_id: str, profession: str, employer: str = "") -> dict:
        character = self.character(character_id)
        self.db.execute(
            "INSERT INTO character_professions (character_id, profession, employer, status, hired_year, years_experience, income, location) VALUES (?, ?, ?, 'active', ?, 0, 0, ?) ON CONFLICT(character_id) DO UPDATE SET profession = excluded.profession, employer = excluded.employer, status = excluded.status, location = excluded.location",
            (character_id, profession, employer or character["origin"], self.date(character["world_id"]).year, character["location_id"]),
        )
        self.db.execute("UPDATE characters SET profession = ? WHERE character_id = ?", (profession, character_id))
        self.log(character["world_id"], character_id, "personal", f"{character['name']} becomes a {profession} in {employer or character['origin']}.", 2)
        return self.db.one("SELECT * FROM character_professions WHERE character_id = ?", (character_id,))

    def train_skill(self, character_id: str, name: str, amount: int = 1) -> dict:
        character = self.character(character_id)
        skill_id = str(uuid.uuid4())
        existing = self.db.one("SELECT * FROM skills WHERE character_id = ? AND name = ?", (character_id, name))
        if existing:
            self.db.execute(
                "UPDATE skills SET level = level + ?, experience = experience + ?, proficiency = MIN(100, proficiency + ?) WHERE skill_id = ?",
                (amount, amount * 10, amount * 5, existing["skill_id"]),
            )
            row = self.db.one("SELECT * FROM skills WHERE skill_id = ?", (existing["skill_id"],))
        else:
            self.db.execute("INSERT INTO skills (skill_id, character_id, name, level, experience, proficiency, specialization, reputation) VALUES (?, ?, ?, ?, ?, ?, 'general', 0)", (skill_id, character_id, name, max(1, amount), amount * 10, amount * 5))
            row = self.db.one("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
        self.log(character["world_id"], character_id, "personal", f"{character['name']} trains {name} and gains practical experience.", 1)
        return row

    def create_business(self, character_id: str, name: str, business_type: str, location: str, capital: int = 50) -> dict:
        character = self.character(character_id)
        business_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO businesses (business_id, world_id, owner_id, name, type, location, capital, revenue, expenses, inventory, reputation, status) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'goods', 0, 'active')", (business_id, character["world_id"], character_id, name, business_type, location, capital))
        self.db.execute("UPDATE characters SET wealth = wealth - ? WHERE character_id = ?", (min(capital, character["wealth"]), character_id))
        self.log(character["world_id"], character_id, "business", f"{character['name']} founds {name}, a {business_type} in {location}.", 3)
        return self.db.one("SELECT * FROM businesses WHERE business_id = ?", (business_id,))

    def buy_property(self, character_id: str, name: str, kind: str, location: str, value: int = 50) -> dict:
        character = self.character(character_id)
        property_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO properties (property_id, world_id, owner_id, name, kind, location, value, condition, status, tax, income) VALUES (?, ?, ?, ?, ?, ?, ?, 100, 'owned', 0, 0)", (property_id, character["world_id"], character_id, name, kind, location, value))
        self.db.execute("UPDATE characters SET wealth = wealth - ? WHERE character_id = ?", (value, character_id))
        self.log(character["world_id"], character_id, "property", f"{character['name']} buys {name}, a {kind} at {location}.", 2)
        return self.db.one("SELECT * FROM properties WHERE property_id = ?", (property_id,))

    def create_marriage(self, character_a: str, character_b: str, kind: str = "love") -> dict:
        char_a = self.character(character_a)
        char_b = self.character(character_b)
        if char_a["world_id"] != char_b["world_id"]:
            raise ValueError("Characters are in different worlds")
        marriage_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO marriages (marriage_id, world_id, spouse_a, spouse_b, status, kind, started_year, ended_year, notes) VALUES (?, ?, ?, ?, 'married', ?, ?, NULL, 'A newly formed union.')", (marriage_id, char_a["world_id"], character_a, character_b, kind, self.date(char_a["world_id"]).year))
        self.log(char_a["world_id"], character_a, "family", f"{char_a['name']} and {char_b['name']} are married.", 3)
        self.log(char_a["world_id"], character_b, "family", f"{char_b['name']} and {char_a['name']} are married.", 3)
        return self.db.one("SELECT * FROM marriages WHERE marriage_id = ?", (marriage_id,))

    def birth_child(self, parent_a: str, parent_b: str, name: str, species: str = "Human", birthplace: str = "Azure Village") -> dict:
        parent1 = self.character(parent_a)
        parent2 = self.character(parent_b)
        if parent1["world_id"] != parent2["world_id"]:
            raise ValueError("Parents are in different worlds")

        family_row = self.db.one("SELECT family_id FROM family_members WHERE character_id = ? LIMIT 1", (parent1["character_id"],))
        family_id = family_row["family_id"] if family_row else self.db.one("SELECT family_id FROM family_members WHERE character_id = ? LIMIT 1", (parent2["character_id"],))
        family_id = family_id["family_id"] if isinstance(family_id, dict) else family_id
        if not family_id:
            family_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO families VALUES (?, ?, ?, ?)", (family_id, parent1["world_id"], f"{parent1['name']} Family", self.date(parent1["world_id"]).year))
        character_id = str(uuid.uuid4())
        location = self.db.one("SELECT location_id FROM locations WHERE world_id = ? AND name = ? LIMIT 1", (parent1["world_id"], birthplace)) or self.db.one("SELECT location_id FROM locations WHERE world_id = ? LIMIT 1", (parent1["world_id"],))
        self.db.execute("INSERT INTO characters (character_id, world_id, name, age, sex, species, origin, profession, background, personality, location_id, birth_year, alive, birthplace, home, short_goal, ambition, family_id) VALUES (?, ?, ?, 0, 'Unknown', ?, ?, 'Child', 'Childhood', 'Curious', ?, ?, 1, ?, ?, 'Learn and grow.', 'Live a meaningful life.', ?)", (character_id, parent1["world_id"], name, species, parent1["origin"], location["location_id"], self.date(parent1["world_id"]).year, birthplace, birthplace, family_id))
        self.db.execute("INSERT INTO family_members (family_id, character_id, role, joined_year, left_year) VALUES (?, ?, 'child', ?, NULL)", (family_id, character_id, self.date(parent1["world_id"]).year))
        self.db.execute("INSERT INTO children (child_id, world_id, child_character_id, parent_a, parent_b, birth_year, birthplace, species, family_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), parent1["world_id"], character_id, parent_a, parent_b, self.date(parent1["world_id"]).year, birthplace, species, family_id))
        self.log(parent1["world_id"], character_id, "family", f"{name} is born to {parent1['name']} and {parent2['name']}.", 3)
        return self.character(character_id)

    def create_organization(self, world_id: str, name: str, org_type: str, owner_id: str | None = None) -> dict:
        organization_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO organizations (organization_id, world_id, owner_id, name, type, status, reputation, treasury, influence) VALUES (?, ?, ?, ?, ?, 'active', 0, 0, 0)", (organization_id, world_id, owner_id, name, org_type))
        return self.db.one("SELECT * FROM organizations WHERE organization_id = ?", (organization_id,))

    def join_organization(self, character_id: str, organization_id: str, rank: str = "member") -> dict:
        self.db.execute("INSERT OR IGNORE INTO organization_members (organization_id, character_id, rank, joined_year) VALUES (?, ?, ?, ?)", (organization_id, character_id, rank, self.date(self.db.one("SELECT world_id FROM organizations WHERE organization_id = ?", (organization_id,))["world_id"]).year))
        return self.db.one("SELECT * FROM organization_members WHERE organization_id = ? AND character_id = ?", (organization_id, character_id))

    def record_life_event(self, character_id: str, category: str, summary: str) -> dict:
        character = self.character(character_id)
        date = self.date(character["world_id"])
        event_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO life_events (event_id, world_id, character_id, category, summary, year, month, day) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (event_id, character["world_id"], character_id, category, summary, date.year, date.month, date.day))
        return self.db.one("SELECT * FROM life_events WHERE event_id = ?", (event_id,))

    def enroll_in_school(self, character_id: str, institution: str = "Village School", curriculum: str = "general") -> dict:
        character = self.character(character_id)
        education_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO education_records (education_id, character_id, institution, curriculum, status, years, mentor, grade) VALUES (?, ?, ?, ?, 'active', 0, NULL, 'apprentice')", (education_id, character_id, institution, curriculum))
        self.log(character["world_id"], character_id, "education", f"{character['name']} begins study at {institution}.", 2)
        return self.db.one("SELECT * FROM education_records WHERE education_id = ?", (education_id,))

    def life_summary(self, character_id: str) -> dict:
        character = self.character(character_id)
        prof = self.db.one("SELECT * FROM character_professions WHERE character_id = ?", (character_id,))
        family = self.db.one("SELECT f.* FROM families f JOIN family_members m ON m.family_id = f.family_id WHERE m.character_id = ?", (character_id,))
        marriage = self.db.one("SELECT * FROM marriages WHERE spouse_a = ? OR spouse_b = ? ORDER BY started_year DESC LIMIT 1", (character_id, character_id))
        skills = self.db.all("SELECT * FROM skills WHERE character_id = ? ORDER BY level DESC", (character_id,))
        events = self.db.all("SELECT category, summary FROM life_events WHERE character_id = ? ORDER BY year DESC, month DESC, day DESC LIMIT 10", (character_id,))
        return {"character": character["name"], "profession": prof["profession"] if prof else character["profession"], "family": family["name"] if family else "None", "marriage": marriage["status"] if marriage else "single", "skills": [row["name"] for row in skills], "events": events}
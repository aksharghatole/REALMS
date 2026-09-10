import random
import uuid
from dataclasses import dataclass

from game.clock import GameDate
from game.cultivation.dao import seed_dao_paths
from game.cultivation.realms import REALMS, realm_name
from game.cultivation.techniques import mastery_name, seed_techniques


CULTIVATION_METHODS = {
    "meditation": {"speed": 1, "risk": 2},
    "absorb qi": {"speed": 2, "risk": 4},
    "body training": {"speed": 1, "risk": 3},
    "train soul": {"speed": 1, "risk": 3},
    "study dao": {"speed": 1, "risk": 2},
}


@dataclass(frozen=True)
class CultivationResult:
    text: str
    progress: int
    risk: int


class CultivationEngine:
    """Calculates cultivation progress from state, methods, environment, and risk."""

    def __init__(self, db, seed: int = 184729):
        self.db = db
        self.seed = seed

    def ensure(self, character_id: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO cultivation_states (character_id) SELECT character_id FROM characters WHERE character_id = ?", (character_id,))
        seed_dao_paths(self.db)
        seed_techniques(self.db)
        default = self.db.one("SELECT technique_id FROM techniques WHERE name = 'Breath of Still Water'")
        if default:
            self.db.execute("INSERT OR IGNORE INTO character_techniques (character_id, technique_id) VALUES (?, ?)", (character_id, default["technique_id"]))

    def state(self, character_id: str):
        self.ensure(character_id)
        return self.db.one("SELECT * FROM cultivation_states WHERE character_id = ?", (character_id,))

    def cultivate(self, character_id: str, method: str = "meditation", days: int = 30) -> CultivationResult:
        state = self.state(character_id)
        character = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        location = self.db.one("SELECT * FROM locations WHERE location_id = ?", (character["location_id"],))
        density = {"village": 1, "city": 1, "sect": 3, "wilderness": 2}.get(location["kind"], 1) if location else 1
        method_key = method.lower()
        speed = {"meditation": 1, "absorb qi": 2, "body training": 1, "train body": 1, "train soul": 1, "study dao": 1}.get(method_key, 1)
        progress = max(1, days // 10) * speed * density + state["cultivation_speed"]
        risk = min(90, max(2, state["cultivation_deviation_risk"] + max(0, days - 60) // 10 - state["soul_stability"] // 20))
        self.db.execute("UPDATE cultivation_states SET cultivation_progress = MIN(100, cultivation_progress + ?), preparation = MIN(100, preparation + ?), tribulation_pressure = MIN(100, tribulation_pressure + ?) WHERE character_id = ?", (progress, max(1, days // 30), max(1, days // 60), character_id))
        if method_key in {"train body", "body training"}:
            self.db.execute("UPDATE cultivation_states SET body_strength = MIN(100, body_strength + 2), body_tempering = MIN(100, body_tempering + 1) WHERE character_id = ?", (character_id,))
        if method_key == "train soul":
            self.db.execute("UPDATE cultivation_states SET soul_strength = MIN(100, soul_strength + 2), soul_stability = MIN(100, soul_stability + 1) WHERE character_id = ?", (character_id,))
        text = f"You practice {method_key} for {days} days. Your progress deepens by {progress}; the change is subtle but real."
        return CultivationResult(text, progress, risk)

    def study_dao(self, character_id: str, dao_name: str = "Sword") -> str:
        self.ensure(character_id)
        dao = self.db.one("SELECT dao_id FROM dao_paths WHERE lower(name) = lower(?)", (dao_name,))
        if dao is None:
            dao_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO dao_paths VALUES (?, ?, 'personal', ?)", (dao_id, dao_name, f"A personal path called {dao_name}."))
        else:
            dao_id = dao["dao_id"]
        self.db.execute("INSERT OR IGNORE INTO character_dao (character_id, dao_id) VALUES (?, ?)", (character_id, dao_id))
        self.db.execute("UPDATE character_dao SET progression = MIN(100, progression + 5), awareness = MIN(100, awareness + 3), understanding = MIN(100, understanding + 1) WHERE character_id = ? AND dao_id = ?", (character_id, dao_id))
        self.db.execute("UPDATE cultivation_states SET dao_comprehension = MIN(100, dao_comprehension + 3), dao_intent = MIN(100, dao_intent + 1) WHERE character_id = ?", (character_id,))
        return f"You contemplate {dao_name} Dao. A small piece of its shape becomes clear."

    def practice_technique(self, character_id: str, technique_name: str = "Breath of Still Water") -> str:
        self.ensure(character_id)
        technique = self.db.one("SELECT * FROM techniques WHERE name LIKE ?", (f"%{technique_name}%",))
        if technique is None:
            return "You do not know that technique."
        state = self.state(character_id)
        if state["realm_id"] < technique["required_realm"]:
            return "Your current realm cannot safely practice that technique."
        self.db.execute("INSERT OR IGNORE INTO character_techniques (character_id, technique_id) VALUES (?, ?)", (character_id, technique["technique_id"]))
        self.db.execute("UPDATE character_techniques SET practice = practice + 1, mastery = MIN(80, mastery + 2) WHERE character_id = ? AND technique_id = ?", (character_id, technique["technique_id"]))
        mastery = self.db.one("SELECT mastery FROM character_techniques WHERE character_id = ? AND technique_id = ?", (character_id, technique["technique_id"]))["mastery"]
        return f"You practice {technique['name']}. Mastery: {mastery_name(mastery)}."

    def breakthrough(self, character_id: str) -> tuple[bool, str, int]:
        state = self.state(character_id)
        if state["realm_id"] >= len(REALMS) - 1:
            return False, "The path has no known higher realm.", 0
        score = state["foundation_quality"] + state["foundation_integrity"] // 2 + state["comprehension"] + state["willpower"] + state["preparation"] + state["dao_comprehension"] - state["karma"] - state["breakthrough_difficulty"]
        chance = max(5, min(92, score // 3))
        roll = random.Random(self.seed + state["realm_id"] * 101 + state["preparation"]).randint(1, 100)
        if roll > chance:
            damage = max(1, min(15, (roll - chance) // 4))
            self.db.execute("UPDATE cultivation_states SET foundation_integrity = MAX(1, foundation_integrity - ?), preparation = 0, cultivation_deviation_risk = MIN(90, cultivation_deviation_risk + 2) WHERE character_id = ?", (damage, character_id))
            return False, f"Your qi recoils. The breakthrough fails and your foundation loses {damage} integrity.", chance
        quality = "Ordinary" if roll > chance - 20 else "Good" if roll > chance - 40 else "Excellent" if roll > chance - 60 else "Perfect"
        bonus = {"Ordinary": 0, "Good": 2, "Excellent": 5, "Perfect": 10}[quality]
        next_realm = state["realm_id"] + (1 if state["internal_level"] >= 4 else 0)
        next_level = 0 if state["internal_level"] >= 4 else state["internal_level"] + 1
        next_stage = ("Early", "Middle", "Late", "Peak", "Perfection")[next_level]
        self.db.execute("UPDATE cultivation_states SET realm_id = ?, internal_level = ?, stage = ?, cultivation_progress = 0, foundation_integrity = MIN(100, foundation_integrity + ?), tribulation_pressure = MIN(100, tribulation_pressure + 5) WHERE character_id = ?", (next_realm, next_level, next_stage, bonus, character_id))
        return True, f"Your qi settles into {realm_name(next_realm, next_level)}. The breakthrough is {quality.lower()}.", chance
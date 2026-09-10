import random
import uuid

TRIBULATION_TYPES = ("Lightning", "Fire", "Wind", "Ice", "Earth", "Sword", "Soul", "Heart Demon", "Blood", "Karma", "Dao", "Five Element", "Nine Heavens Lightning", "Void", "Space-Time", "Samsara", "Causality", "Heavenly Dao", "Great Destruction", "World", "Star", "Heavenly Execution", "Epoch", "Unknown")
TRIBULATION_TIERS = ("Mortal", "Spirit", "Earth", "Heavenly", "Nine Heavens", "Destruction", "Chaos", "Primordial", "Annihilation", "Unknown")


class TribulationEngine:
    def __init__(self, db, seed: int = 184729):
        self.db, self.seed = db, seed

    def generate(self, character_id: str) -> dict:
        state = self.db.one("SELECT * FROM cultivation_states WHERE character_id = ?", (character_id,))
        if state is None:
            raise ValueError("Cultivation state is not initialized")
        rng = random.Random(self.seed + state["realm_id"] * 31 + state["tribulation_pressure"])
        kind = TRIBULATION_TYPES[rng.randrange(min(len(TRIBULATION_TYPES), max(4, state["realm_id"] + 4)))]
        tier = TRIBULATION_TIERS[min(len(TRIBULATION_TIERS) - 1, state["realm_id"] // 5)]
        severity = max(1, min(100, 15 + state["realm_id"] * 2 + state["karma"] // 2 + state["tribulation_pressure"] - state["luck"] // 5))
        spotting = state["perception"] + state["tribulation_spotting"] + state["soul_strength"] // 3
        tribulation_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO tribulations VALUES (?, ?, ?, ?, ?, ?, 'forming', 0, '')", (tribulation_id, character_id, kind, tier, severity, spotting))
        return {"tribulation_id": tribulation_id, "type": kind, "tier": tier, "severity": severity, "spotting": spotting}

    def warning(self, character_id: str) -> str:
        row = self.db.one("SELECT * FROM tribulations WHERE character_id = ? AND status = 'forming' ORDER BY rowid DESC LIMIT 1", (character_id,))
        if row is None:
            return "The spiritual air is quiet."
        return "You detect a change in spiritual pressure." if row["spotting"] < 60 else f"You detect a {row['type']} tribulation forming within the next several hours."

    def resolve(self, character_id: str, action: str) -> str:
        row = self.db.one("SELECT * FROM tribulations WHERE character_id = ? AND status = 'forming' ORDER BY rowid DESC LIMIT 1", (character_id,))
        if row is None:
            return "No tribulation is currently forming."
        state = self.db.one("SELECT * FROM cultivation_states WHERE character_id = ?", (character_id,))
        defense = state["foundation_integrity"] + state["soul_stability"] + state["tribulation_spotting"]
        if action.lower() in {"defend", "use formation", "endure"}:
            defense += 15
        success = defense + state["luck"] > row["severity"] * 2
        if success:
            self.db.execute("UPDATE tribulations SET status = 'survived', consequences = 'Dao pressure leaves an insight.' WHERE tribulation_id = ?", (row["tribulation_id"],))
            self.db.execute("UPDATE cultivation_states SET tribulation_pressure = MAX(0, tribulation_pressure - 20), dao_comprehension = MIN(100, dao_comprehension + 4) WHERE character_id = ?", (character_id,))
            return f"You survive the {row['type']} tribulation. The pressure leaves a sharp insight behind."
        damage = max(1, row["severity"] // 8)
        self.db.execute("UPDATE tribulations SET status = 'failed', damage = ?, consequences = 'Foundation damaged.' WHERE tribulation_id = ?", (damage, row["tribulation_id"]))
        self.db.execute("UPDATE cultivation_states SET foundation_integrity = MAX(1, foundation_integrity - ?), soul_stability = MAX(1, soul_stability - ?) WHERE character_id = ?", (damage, max(1, damage // 2), character_id))
        self.db.execute("INSERT INTO injuries VALUES (?, ?, 'Foundation Damage', ?, 60, ?, 1)", (str(uuid.uuid4()), character_id, damage, row["type"]))
        return f"The {row['type']} tribulation breaks through your defenses. Your foundation is damaged."
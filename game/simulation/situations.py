import random
import uuid

from game.clock import GameDate
from game.database.db import Database


class SituationEngine:
    """Creates a few contextual situations instead of a fixed quest list."""

    def __init__(self, db: Database, seed: int = 184729):
        self.db = db
        self.seed = seed

    def refresh(self, character_id: str) -> None:
        character = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        if character is None or not character["alive"]:
            return
        open_count = self.db.one("SELECT COUNT(*) AS count FROM situations WHERE character_id = ? AND status = 'open'", (character_id,))["count"]
        if open_count >= 3:
            return
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (character["world_id"],))
        date = GameDate(world["year"], world["month"], world["day"], world["hour"])
        location = self.db.one("SELECT * FROM locations WHERE location_id = ?", (character["location_id"],))
        rng = random.Random(self.seed + character["age"] * 31 + date.day_of_year + open_count * 17)
        choices = []
        if character["profession"] == "Farmer" and date.weather(self.seed) in {"Rain", "Storm", "Heavy Rain"}:
            choices.append(("broken_irrigation", "Broken irrigation channel", "A neighboring farmer asks for help before the rain washes away the field wall.", "help|ignore|demand payment|investigate", 3))
        if character["profession"] in {"Merchant", "Farmer"}:
            choices.append(("market_offer", "A caravan needs help", "A merchant offers honest pay for carrying grain to Eastern Market.", "accept|ignore|negotiate", 2))
        if location and location["kind"] == "wilderness":
            choices.append(("strange_tracks", "Strange tracks in the forest", "Fresh tracks vanish beneath the trees. They might belong to a beast, a traveler, or something less ordinary.", "investigate|ignore|report", 4))
        if not choices:
            choices.append(("traveler", "A traveler asks a question", "A dusty traveler wants directions and watches your answer closely.", "help|ignore|question", 1))
        kind, title, description, available_choices, urgency = rng.choice(choices)
        duplicate = self.db.one("SELECT situation_id FROM situations WHERE character_id = ? AND kind = ? AND status = 'open'", (character_id, kind))
        if duplicate is None:
            self.db.execute("INSERT INTO situations (situation_id, world_id, character_id, location_id, kind, title, description, choices, status, urgency, created_year, created_month, created_day, expires_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)", (str(uuid.uuid4()), character["world_id"], character_id, character["location_id"], kind, title, description, available_choices, urgency, date.year, date.month, date.day, date.day + 30))

    def list_open(self, character_id: str) -> list:
        return self.db.all("SELECT * FROM situations WHERE character_id = ? AND status = 'open' ORDER BY urgency DESC, created_day DESC", (character_id,))

    def resolve(self, character_id: str, situation_id: str, choice: str) -> str:
        situation = self.db.one("SELECT * FROM situations WHERE situation_id = ? AND character_id = ? AND status = 'open'", (situation_id, character_id))
        if situation is None:
            return "That situation is no longer open."
        if choice.lower() not in situation["choices"].split("|"):
            return "That is not an available choice."
        character = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        self.db.execute("UPDATE situations SET status = ? WHERE situation_id = ?", ("resolved", situation_id))
        if choice.lower() in {"help", "accept", "negotiate"}:
            self.db.execute("UPDATE characters SET reputation = MIN(100, reputation + 2), morale = MIN(100, morale + 2), wealth = wealth + 3 WHERE character_id = ?", (character_id,))
            return f"You choose to {choice.lower()}. The situation improves, and people remember your decision."
        if choice.lower() in {"investigate", "question"}:
            self.db.execute("UPDATE characters SET fatigue = MIN(100, fatigue + 4) WHERE character_id = ?", (character_id,))
            return "You investigate carefully. You learn something useful, though the matter is not fully settled."
        return "You leave the matter alone. Someone else will decide what happens next."
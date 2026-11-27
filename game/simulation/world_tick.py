import uuid

from game.clock import GameDate
from game.database.db import Database


class WorldTick:
    """Advances world time and applies cheap scheduled simulation updates."""

    def __init__(self, db: Database, seed: int = 184729, economic_step=None):
        self.db = db
        self.seed = seed
        self.economic_step = economic_step
        self.transport_step = None

    def _advance_survival(self, world_id: str, old: GameDate, days: int) -> None:
        """Apply daily deprivation without iterating over years after a life ends."""
        for row in self.db.all("SELECT character_id, name, hunger, thirst, fatigue, health, age FROM characters WHERE world_id = ? AND alive = 1", (world_id,)):
            hunger, thirst, health = row["hunger"], row["thirst"], row["health"]
            cause = None
            elapsed = 0
            while elapsed < days:
                elapsed += 1
                hunger = max(0, hunger - 5)
                thirst = max(0, thirst - 7)
                health = max(0, health - (1 if hunger == 0 else 0) - (2 if thirst == 0 else 0))
                if health == 0:
                    cause = "starvation and dehydration" if hunger == 0 and thirst == 0 else "dehydration" if thirst == 0 else "starvation" if hunger == 0 else "critical injuries"
                    break
            fatigue = min(100, row["fatigue"] + elapsed * 4)
            cid = row["character_id"]
            if cause is None:
                self.db.execute("UPDATE characters SET hunger = ?, thirst = ?, fatigue = ?, health = ? WHERE character_id = ?", (hunger, thirst, fatigue, health, cid))
                continue
            death = old.advance(elapsed * 24 - old.hour)
            self.db.execute("UPDATE characters SET hunger = ?, thirst = ?, fatigue = ?, health = 0, alive = 0, age = ?, death_date = ?, death_cause = ? WHERE character_id = ?", (hunger, thirst, fatigue, row["age"] + death.year - old.year, death.text(), cause, cid))
            self.db.execute("INSERT INTO events VALUES (?, ?, ?, 'death', ?, ?, ?, ?, 5)", (str(uuid.uuid4()), world_id, cid, f"{row['name']} died by {cause}.", death.year, death.month, death.day))

    def advance(self, world_id: str, hours: int) -> GameDate:
        world = self.db.one("SELECT * FROM worlds WHERE world_id = ?", (world_id,))
        if world is None:
            raise ValueError("Unknown world")
        old = GameDate(world["year"], world["month"], world["day"], world["hour"])
        current = old.advance(hours)
        self.db.execute("UPDATE worlds SET year = ?, month = ?, day = ?, hour = ? WHERE world_id = ?", (current.year, current.month, current.day, current.hour, world_id))
        old_serial = (old.year - 1) * 360 + old.day_of_year
        current_serial = (current.year - 1) * 360 + current.day_of_year
        days_elapsed = max(0, current_serial - old_serial)
        if days_elapsed:
            self._advance_survival(world_id, old, days_elapsed)
            self.db.execute("UPDATE npcs SET hunger = MAX(0, hunger - ?), fatigue = MIN(100, fatigue + ?) WHERE world_id = ? AND alive = 1", (days_elapsed * 5, days_elapsed * 4, world_id))
        if current != old:
            self.db.execute("UPDATE npcs SET routine = CASE WHEN ? BETWEEN 6 AND 17 THEN 'work' WHEN ? BETWEEN 18 AND 21 THEN 'home' ELSE 'sleep' END WHERE world_id = ? AND alive = 1", (current.hour, current.hour, world_id))
        years_elapsed = current.year - old.year
        if years_elapsed:
            self.db.execute("UPDATE characters SET age = age + ? WHERE world_id = ? AND alive = 1", (years_elapsed, world_id))
            self.db.execute("UPDATE npcs SET age = age + ? WHERE world_id = ? AND alive = 1", (years_elapsed, world_id))
        if days_elapsed and self.economic_step is not None:
            self.economic_step(world_id, days_elapsed)
        if days_elapsed and self.transport_step is not None:
            self.transport_step(world_id, days_elapsed)
        return current
from game.clock import GameDate
from game.database.db import Database


class WorldTick:
    """Advances world time and applies cheap scheduled simulation updates."""

    def __init__(self, db: Database, seed: int = 184729, economic_step=None):
        self.db = db
        self.seed = seed
        self.economic_step = economic_step
        self.transport_step = None

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
            self.db.execute("UPDATE characters SET hunger = MAX(0, hunger - ?), thirst = MAX(0, thirst - ?), fatigue = MIN(100, fatigue + ?), health = MAX(0, health - CASE WHEN hunger < 10 OR thirst < 10 THEN 2 ELSE 0 END) WHERE world_id = ? AND alive = 1", (days_elapsed * 5, days_elapsed * 7, days_elapsed * 4, world_id))
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
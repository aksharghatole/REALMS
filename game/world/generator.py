import random
import uuid

from game.database.db import Database


class WorldGenerator:
    """Creates a compact deterministic starting world and its important NPCs."""

    def __init__(self, database: Database):
        self.db = database

    def create(self, seed: int, name: str = "Azure Heaven") -> str:
        world_id = str(uuid.uuid4())
        rng = random.Random(seed)
        self.db.execute("INSERT INTO worlds VALUES (?, ?, ?, 1, 1, 1, 6)", (world_id, name, seed))
        locations = [
            ("Azure Village", "village", "A quiet farming village beneath the eastern hills.", 0, "fields", 1),
            ("Eastern Market", "city", "A busy market where grain, tools, and rumors change hands.", 3, "road", 2),
            ("Whispering Forest", "wilderness", "Old trees crowd around paths leading into uncertain country.", 5, "forest", 6),
            ("Cloudstep Sect", "sect", "A modest cultivation sect built on a cliff above the river.", 7, "mountain", 4),
        ]
        ids: dict[str, str] = {}
        for location_name, kind, description, distance, terrain, danger in locations:
            location_id = str(uuid.uuid4())
            ids[location_name] = location_id
            self.db.execute("INSERT INTO locations (location_id, world_id, name, kind, description, parent_id, distance, terrain, danger) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)", (location_id, world_id, location_name, kind, description, distance, terrain, danger))
        faction_rows = [(str(uuid.uuid4()), world_id, "Cloudstep Sect", "Sect", 800, 20), (str(uuid.uuid4()), world_id, "Azure Kingdom", "Kingdom", 2500, 10)]
        self.db.executemany("INSERT INTO factions VALUES (?, ?, ?, ?, ?, ?)", faction_rows)
        faction_id = faction_rows[0][0]
        for index, (from_name, to_name) in enumerate((("Azure Village", "Eastern Market"), ("Azure Village", "Whispering Forest"), ("Azure Village", "Cloudstep Sect"))):
            self.db.execute("INSERT INTO routes VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), world_id, from_name, to_name, locations[index + 1][3], locations[index + 1][4], locations[index + 1][5], max(0, locations[index + 1][3] // 2)))
        names = ["Old Han", "Mei Lin", "Qiao Ren", "Tao Yun", "Master Shen", "Bao Jun", "Lan Yue"]
        professions = ["Farmer", "Merchant", "Blacksmith", "Doctor", "Scholar", "Guard", "Sect Servant"]
        for index, (npc_name, profession) in enumerate(zip(names, professions)):
            npc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{seed}:npc:{index}"))
            self.db.execute("INSERT INTO npcs (npc_id, world_id, name, age, sex, species, location_id, faction_id, profession, wealth) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (npc_id, world_id, npc_name, rng.randint(19, 72), "F", "Human", ids["Azure Village" if index < 4 else "Cloudstep Sect"], faction_id if index >= 4 else None, profession, rng.randint(8, 90)))
        return world_id
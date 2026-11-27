"""Seeded, bounded discoveries that extend the persisted route network."""
import random
import uuid

SITES = (
    ("Reed Crossing", "hamlet", "A few homes stand beside a shallow river crossing.", "riverbank", 1),
    ("Jade Spring", "spring", "Clear water flows through moss-covered stones.", "hills", 1),
    ("Pine Hollow", "wilderness", "A secluded hollow lies beneath ancient pines.", "forest", 3),
    ("Silent Shrine", "ruins", "Weathered inscriptions surround a forgotten shrine.", "ruins", 4),
    ("Mistwatch Hamlet", "hamlet", "Small farms cling to the sheltered hillside.", "hills", 2),
    ("Moonstone Quarry", "quarry", "Abandoned workings reveal pale seams of stone.", "rocky hills", 3),
    ("Willow Ford", "crossing", "A narrow path winds past willows and stepping stones.", "riverbank", 2),
    ("Redleaf Grove", "wilderness", "Rust-colored leaves cover a quiet forest trail.", "forest", 3),
)
PREFIXES = ("Eastern", "Hidden", "Silver", "Ancient", "Quiet", "Northern", "Distant", "Misty")
MAX_WORLD_LOCATIONS = 48
MAX_LOCAL_DISCOVERIES = 2
EXPLORATION_HOURS = 6
EXPLORATION_FATIGUE = 12


def remaining_discoveries(db, world_id, origin_id):
    total = db.one("SELECT COUNT(*) AS n FROM locations WHERE world_id = ?", (world_id,))["n"]
    children = db.one("SELECT COUNT(*) AS n FROM locations WHERE world_id = ? AND parent_id = ?", (world_id, origin_id))["n"]
    return max(0, min(MAX_WORLD_LOCATIONS - total, MAX_LOCAL_DISCOVERIES - children))


def discover(db, world_id, origin):
    """Create a location and its route together, or return None at the limit."""
    if not remaining_discoveries(db, world_id, origin["location_id"]):
        return None
    seed = db.one("SELECT seed FROM worlds WHERE world_id = ?", (world_id,))["seed"]
    index = db.one("SELECT COUNT(*) AS n FROM locations WHERE world_id = ? AND parent_id = ?", (world_id, origin["location_id"]))["n"]
    rng = random.Random(f"{seed}:{origin['name']}:{index}")
    site, kind, description, terrain, danger = rng.choice(SITES)
    names = [site] + [f"{prefix} {site}" for prefix in rng.sample(PREFIXES, len(PREFIXES))]
    name = next((candidate for candidate in names if not db.one("SELECT 1 FROM locations WHERE world_id = ? AND name = ?", (world_id, candidate))), None)
    if name is None:
        number = 2
        while db.one("SELECT 1 FROM locations WHERE world_id = ? AND name = ?", (world_id, f"{site} {number}")):
            number += 1
        name = f"{site} {number}"
    distance = rng.randint(1, 3)
    location_id, route_id = str(uuid.uuid4()), str(uuid.uuid4())
    with db.connection:
        db.connection.execute(
            "INSERT INTO locations (location_id, world_id, name, kind, description, parent_id, distance, terrain, danger) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (location_id, world_id, name, kind, description, origin["location_id"], distance, terrain, danger),
        )
        db.connection.execute(
            "INSERT INTO routes (route_id, world_id, from_location, to_location, distance, terrain, danger, travel_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (route_id, world_id, origin["name"], name, distance, terrain, danger, distance // 2),
        )
    return name

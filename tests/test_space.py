import tempfile

from game.database.db import Database
from game.engine import GameEngine


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 123)
    world = engine.create_world()
    return handle, db, engine, world


def test_universe_generation_and_planet_persistence():
    handle, db, engine, world = make_engine()

    universe = engine.create_universe("Azure Universe")
    galaxy = engine.create_galaxy(universe["universe_id"], "spiral")
    system = engine.create_star_system(galaxy["galaxy_id"], "Helios Reach")
    planet = engine.create_planet(system["system_id"], "Veyra Prime")

    assert universe["name"] == "Azure Universe"
    assert galaxy["type"] == "spiral"
    assert system["name"] == "Helios Reach"
    assert planet["name"] == "Veyra Prime"
    assert db.one("SELECT COUNT(*) AS count FROM planets WHERE planet_id = ?", (planet["planet_id"],))["count"] == 1

    handle.close()


def test_spacecraft_and_route_travel():
    handle, db, engine, world = make_engine()
    universe = engine.create_universe("Azure Universe")
    galaxy = engine.create_galaxy(universe["universe_id"], "barred spiral")
    system = engine.create_star_system(galaxy["galaxy_id"], "Helios Reach")
    planet_a = engine.create_planet(system["system_id"], "Aster")
    planet_b = engine.create_planet(system["system_id"], "Borealis")
    ship = engine.create_spacecraft("Explorer One", owner_id=None, ship_type="exploration vessel", current_location=planet_a["planet_id"])
    route = engine.create_space_route("trade", planet_a["planet_id"], planet_b["planet_id"], distance=12)
    journey = engine.launch_spacecraft(ship["ship_id"], route["route_id"], fuel=10)

    assert ship["ship_id"]
    assert route["distance"] == 12
    assert journey["status"] in {"launched", "in_transit", "arrived"}

    handle.close()

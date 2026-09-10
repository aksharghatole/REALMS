import tempfile

from game.database.db import Database
from game.engine import GameEngine


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_journey_persists_and_arrives_after_elapsed_time():
    handle, db, engine, world = make_engine()
    traveler = engine.create_character(world, "Wei")
    journey = engine.plan_journey(traveler, "Azure Village", "Eastern Market", "walking")
    assert journey["status"] == "PLANNED"
    assert journey["estimated_hours"] > 0
    engine.depart_journey(journey["journey_id"])
    assert db.one("SELECT status FROM journeys WHERE journey_id = ?", (journey["journey_id"],))["status"] == "IN_TRANSIT"
    engine.tick.advance(world, journey["estimated_hours"])
    arrived = db.one("SELECT status FROM journeys WHERE journey_id = ?", (journey["journey_id"],))
    assert arrived["status"] == "ARRIVED"
    assert engine.character(traveler)["location_id"] == db.one("SELECT location_id FROM locations WHERE name = 'Eastern Market'")['location_id']
    handle.close()


def test_messages_are_delayed_and_persistent():
    handle, db, engine, world = make_engine()
    sender = engine.create_character(world, "Sender")
    receiver = engine.create_character(world, "Receiver")
    message = engine.send_message(sender, receiver, "The road is unsafe.", method="courier")
    assert message["status"] == "IN_TRANSIT"
    assert db.one("SELECT COUNT(*) AS count FROM messages WHERE message_id = ?", (message["message_id"],))["count"] == 1
    engine.tick.advance(world, message["delivery_hours"])
    delivered = engine.inbox(receiver)
    assert delivered[0]["status"] == "DELIVERED"
    assert delivered[0]["content"] == "The road is unsafe."
    handle.close()


def test_cargo_and_warehouse_move_through_route():
    handle, db, engine, world = make_engine()
    warehouse = engine.create_warehouse(world, "Village Granary", "Azure Village", capacity=100)
    cargo = engine.create_cargo(world, "grain", 10, "Azure Village", "Eastern Market", owner_id="merchant")
    journey = engine.plan_cargo_journey(cargo["cargo_id"], "walking")
    engine.depart_journey(journey["journey_id"])
    engine.tick.advance(world, journey["estimated_hours"])
    assert db.one("SELECT status FROM cargo WHERE cargo_id = ?", (cargo["cargo_id"],))["status"] == "DELIVERED"
    assert db.one("SELECT capacity FROM warehouses WHERE warehouse_id = ?", (warehouse["warehouse_id"],))["capacity"] == 100
    handle.close()


def test_infrastructure_maintenance_degrades_and_repairs():
    handle, db, engine, world = make_engine()
    infrastructure = engine.create_infrastructure(world, "Old Bridge", "bridge", "Azure Village", condition=100)
    engine.maintain_infrastructure(infrastructure["infrastructure_id"], days=30)
    assert db.one("SELECT condition FROM infrastructure WHERE infrastructure_id = ?", (infrastructure["infrastructure_id"],))["condition"] < 100
    engine.repair_infrastructure(infrastructure["infrastructure_id"], 20)
    assert db.one("SELECT condition FROM infrastructure WHERE infrastructure_id = ?", (infrastructure["infrastructure_id"],))["condition"] > 70
    handle.close()

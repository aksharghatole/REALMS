from game.engine import GameEngine
from game.database.db import Database
import tempfile


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix='.db')
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_military_unit_creation_and_recruitment():
    handle, db, engine, world = make_engine()
    leader = engine.create_character(world, "General Han")
    unit = engine.create_military_unit(world, "Red Banner Company", unit_type="infantry", commander_id=leader)
    recruit = engine.create_character(world, "Xiao")
    engine.recruit_character_to_unit(recruit, unit["unit_id"], role="soldier")
    row = db.one("SELECT * FROM military_unit_members WHERE unit_id = ? AND character_id = ?", (unit["unit_id"], recruit))
    assert row is not None
    assert row["role"] == "soldier"
    assert unit["unit_type"] == "infantry"
    handle.close()


def test_military_campaign_and_battle_and_supply_route():
    handle, db, engine, world = make_engine()
    attacker = engine.create_organization(world, "Northern League", "army")
    defender = engine.create_organization(world, "Azure Kingdom", "government")
    campaign = engine.create_campaign(world, attacker["organization_id"], defender["organization_id"], objective="capture city")
    battle = engine.create_battle(world, "North Gate", campaign["campaign_id"], "capture city")
    route = engine.create_supply_route(world, "North Road", "Northern Granary", "North Gate", "active")
    assert campaign["objective"] == "capture city"
    assert battle["location"] == "North Gate"
    assert route["status"] == "active"
    handle.close()


def test_command_and_military_actions_parse_and_execute():
    handle, _, engine, world = make_engine()
    soldier = engine.create_character(world, "Rui")
    unit = engine.create_military_unit(world, "Shade Watch", unit_type="scouts", commander_id=soldier)
    action = engine.perform(soldier, "join the army")
    assert "army" in action.lower() or "joined" in action.lower()
    result = engine.execute_military_order(soldier, unit["unit_id"], "defend")
    assert "defend" in result.lower() or "ordered" in result.lower()
    handle.close()

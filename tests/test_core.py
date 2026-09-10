import tempfile

from game.combat.combat import Combat, Combatant
from game.database.db import Database
from game.engine import GameEngine
from game.ai.provider import FallbackAIProvider


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_world_and_character_persist():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    assert db.one("SELECT name FROM worlds WHERE world_id = ?", (world,))["name"] == "Azure Heaven"
    assert db.one("SELECT name FROM characters WHERE character_id = ?", (character,))["name"] == "Wei"
    assert db.one("SELECT COUNT(*) AS count FROM npcs WHERE world_id = ?", (world,))["count"] == 7
    handle.close()


def test_actions_advance_time_and_pay():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    engine.perform(character, "work for 5 days")
    assert engine.date(world).day == 6
    assert engine.character(character)["wealth"] == 30
    handle.close()


def test_breakthrough_and_permanent_death():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    result = engine.attempt_breakthrough(character)
    assert result
    engine.kill_character(character, "a test")
    assert engine.character(character)["alive"] == 0
    assert "test" in engine.character(character)["death_cause"]
    handle.close()


def test_combat_is_deterministic_and_tactical():
    combat = Combat(Combatant("Wei", 100, 20, 12), Combatant("Bandit", 20, 10, 5), seed=4)
    message = combat.act("attack")
    assert "damage" in message
    assert combat.enemy.health < 20


def test_talking_creates_relationship_and_family_persists():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    message = engine.perform(character, "talk to Old Han")
    assert "Old Han" in message
    relationship = engine.relationships(character)[0]
    assert relationship["familiarity"] == 5
    family = engine.family(character)
    assert family["name"] == "The Wei Family"
    assert db.one("SELECT COUNT(*) AS count FROM memories WHERE owner_id = ?", (character,))["count"] == 1
    handle.close()


def test_needs_weather_situations_and_trade():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    before = engine.character(character)
    message = engine.perform(character, "work for 5 days")
    after = engine.character(character)
    assert after["fatigue"] > before["fatigue"]
    assert engine.date(world).season == "Spring"
    assert engine.date(world).weather(engine.seed)
    assert engine.open_situations(character)
    assert "buy" in engine.perform(character, "buy rice")
    assert engine.character(character)["wealth"] == 27
    handle.close()


def test_route_travel_and_journal():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    message = engine.perform(character, "travel to Eastern Market")
    assert "arrive" in message
    current = engine.character(character)
    assert engine.db.one("SELECT name FROM locations WHERE location_id = ?", (current["location_id"],))["name"] == "Eastern Market"
    assert "events" in engine.journal(character)
    assert "Eastern Market" in engine.map_text(world, current["location_id"])
    handle.close()


def test_grounded_free_form_conversation_persists_and_has_boundaries():
    handle, db, engine, world = make_engine()
    engine.set_ai_provider(FallbackAIProvider())
    character = engine.create_character(world, "Wei")
    npc = engine.nearby_npcs(character)[0]
    response = engine.converse(character, npc["npc_id"], "Who is the strongest person in the northern ruins?")
    assert response
    assert "do not know" in response.lower()
    assert db.one("SELECT COUNT(*) AS count FROM conversation_messages")["count"] == 2
    assert db.one("SELECT COUNT(*) AS count FROM memories WHERE owner_id = ?", (npc["npc_id"],))["count"] == 1
    engine.converse(character, npc["npc_id"], "I promise I will help you.")
    relation = db.one("SELECT trust FROM relationships WHERE source_id = ? AND target_id = ?", (character, npc["npc_id"]))
    assert relation["trust"] >= 4
    handle.close()


def test_deep_cultivation_dao_technique_and_tribulation():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    state_before = engine.cultivation_state(character)
    result = engine.cultivation.cultivate(character, "meditation", 30)
    assert result.progress > 0
    assert engine.study_dao(character, "Sword")
    assert engine.practice_technique(character)
    state_after = engine.cultivation_state(character)
    assert state_after["dao_comprehension"] > state_before["dao_comprehension"]
    tribulation = engine.generate_tribulation(character)
    assert tribulation["type"]
    assert engine.tribulation_warning(character)
    assert db.one("SELECT COUNT(*) AS count FROM techniques")["count"] >= 3
    handle.close()


def test_engine_combat_uses_profile_and_records_outcome():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    npc = engine.nearby_npcs(character)[0]
    combat = engine.start_combat(character, npc["npc_id"])
    assert combat.distance == 6
    assert "meters" in combat.visible_enemy()
    message = engine.combat_action(character, "observe")
    assert message
    handle.close()
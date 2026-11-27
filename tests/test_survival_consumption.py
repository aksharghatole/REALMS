import pytest

from game.engine import GameEngine


@pytest.fixture
def game(tmp_path):
    engine = GameEngine.open(tmp_path / "survival.db", 42)
    world = engine.create_world()
    character = engine.create_character(world, "Wei")
    yield engine, world, character
    engine.db.close()


def quantity(engine, character, item):
    return engine.db.one("SELECT quantity FROM inventories WHERE character_id = ? AND item = ?", (character, item))["quantity"]


def test_eat_and_drink_restore_needs_and_consume_supplies(game):
    engine, world, character = game
    engine.db.execute("UPDATE characters SET hunger = 20, thirst = 70 WHERE character_id = ?", (character,))
    start = engine.date(world)
    assert "nourished" in engine.perform(character, "eat food")
    assert engine.character(character)["hunger"] == 55
    assert engine.character(character)["thirst"] == 70
    assert quantity(engine, character, "Food") == 4
    assert "refreshed" in engine.perform(character, "drink water")
    assert engine.character(character)["thirst"] == 100
    assert quantity(engine, character, "Water") == 4
    assert engine.date(world) == start.advance(2)


def test_missing_supplies_or_full_needs_do_not_advance_time(game):
    engine, world, character = game
    engine.db.execute("UPDATE characters SET hunger = 20, thirst = 100 WHERE character_id = ?", (character,))
    engine.db.execute("UPDATE inventories SET quantity = 0 WHERE character_id = ? AND item = 'Food'", (character,))
    before = engine.date(world)
    assert "no food" in engine.perform(character, "eat")
    assert "already hydrated" in engine.perform(character, "drink")
    assert "only eat food" in engine.perform(character, "eat iron")
    assert engine.date(world) == before
    assert quantity(engine, character, "Food") == 0
    assert quantity(engine, character, "Water") == 5
    assert engine.character(character)["hunger"] == 20


def test_existing_character_can_buy_water(game):
    engine, world, character = game
    engine.db.execute("DELETE FROM inventories WHERE character_id = ? AND item = 'Water'", (character,))
    assert "buy" in engine.perform(character, "buy water")
    assert quantity(engine, character, "Water") == 1
    assert "refreshed" in engine.perform(character, "drink")
    assert quantity(engine, character, "Water") == 0

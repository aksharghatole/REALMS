import pytest

from game.engine import GameEngine


@pytest.fixture
def game(tmp_path):
    engine = GameEngine.open(tmp_path / "calendar.db", 42)
    world = engine.create_world()
    yield engine, world
    engine.db.connection.close()


def test_aging_across_multiple_years_and_new_birth_year(game):
    engine, world = game
    alive = engine.create_character(world, "Wei", age=20)
    dead = engine.create_character(world, "Lost", age=30)
    engine.kill_character(dead, "test")
    npc = engine.db.one("SELECT npc_id, age FROM npcs WHERE world_id = ?", (world,))
    # Isolate calendar behavior from economy/transport callbacks.
    engine.tick.economic_step = None
    engine.tick.transport_step = None
    engine.tick.advance(world, 2 * 360 * 24)
    assert engine.date(world).year == 3
    assert engine.character(alive)["age"] == 22
    assert engine.character(dead)["age"] == 30
    assert engine.db.one("SELECT age FROM npcs WHERE npc_id = ?", (npc["npc_id"],))["age"] == npc["age"] + 2
    new = engine.create_character(world, "New", age=18)
    assert engine.character(new)["birth_year"] == 3 - 18


def test_npc_routines_update_within_a_single_day(game):
    engine, world = game
    npc = engine.db.one("SELECT npc_id FROM npcs WHERE world_id = ?", (world,))
    def routine():
        return engine.db.one("SELECT routine FROM npcs WHERE npc_id = ?", (npc["npc_id"],))["routine"]

    assert engine.date(world).hour == 6
    engine.tick.advance(world, 12)
    assert engine.date(world).day == 1
    assert routine() == "home"
    engine.tick.advance(world, 4)
    assert routine() == "sleep"
    engine.tick.advance(world, 8)
    assert routine() == "work"

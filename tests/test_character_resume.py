from game.engine import GameEngine


def test_living_characters_resume_after_reopening_database(tmp_path):
    path = tmp_path / "world.db"
    engine = GameEngine.open(path, 42)
    world = engine.create_world()
    first = engine.create_character(world, "Zhen")
    second = engine.create_character(world, "An", profession="Merchant")
    dead = engine.create_character(world, "Lost")
    engine.save(world, dead)
    engine.kill_character(dead, "test")
    engine.perform(first, "work for 5 days")
    wealth = engine.character(first)["wealth"]
    engine.db.connection.close()

    reopened = GameEngine.open(path, 42)
    try:
        assert reopened.create_world() == world
        living = reopened.living_characters(world)
        assert [row["character_id"] for row in living] == [second, first]
        assert living[0]["profession"] == "Merchant"
        assert reopened.character(first)["wealth"] == wealth
        assert not reopened.character(dead)["alive"]
        assert reopened.living_characters("unknown-world") == []
    finally:
        reopened.db.connection.close()

from game.engine import GameEngine


def test_world_map_uses_persisted_routes(tmp_path):
    engine = GameEngine.open(tmp_path / "map.db", 42)
    try:
        world = engine.create_world()
        cid = engine.create_character(world, "Wei")
        location = engine.character(cid)["location_id"]
        before = engine.map_text(world, location)
        assert "[YOU] Azure Village" in before
        assert "Eastern Market (3 days walking)" in before
        assert "Old Road" not in before
        engine.db.execute(
            "INSERT INTO locations (location_id, world_id, name, kind, description, parent_id, distance, terrain, danger) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)",
            ("new-road", world, "Old Road", "road", "An old road.", 2, "road", 1),
        )
        assert "Old Road\n  No known routes" in engine.map_text(world, location)
        engine.create_route(world, "Azure Village", "Old Road", 2)
        after = engine.map_text(world, location)
        assert "Old Road (2 days walking)" in after
        engine.perform(cid, "travel to Eastern Market")
        current = engine.character(cid)["location_id"]
        assert "[YOU] Eastern Market" in engine.map_text(world, current)
        assert "[YOU] Azure Village" not in engine.map_text(world, current)
        assert "You are here: Unknown" in engine.map_text(world, "unknown")
    finally:
        engine.db.close()

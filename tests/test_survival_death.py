from game.engine import GameEngine


def test_deprivation_damage_matches_daily_and_batched_ticks(tmp_path):
    snapshots = []
    for mode in ("batch", "daily"):
        engine = GameEngine.open(tmp_path / f"{mode}.db", 42)
        try:
            world = engine.create_world()
            cid = engine.create_character(world, "Wei")
            engine.db.execute("UPDATE characters SET hunger = 10, thirst = 14 WHERE character_id = ?", (cid,))
            if mode == "batch":
                engine.tick.advance(world, 5 * 24)
            else:
                for _ in range(5):
                    engine.tick.advance(world, 24)
            row = engine.character(cid)
            snapshots.append(tuple(row[key] for key in ("health", "hunger", "thirst", "fatigue", "alive")))
        finally:
            engine.db.close()
    assert snapshots[0] == snapshots[1] == (88, 0, 0, 30, 1)


def test_deprivation_death_is_permanent_and_recorded_once(tmp_path):
    path = tmp_path / "death.db"
    engine = GameEngine.open(path, 42)
    world = engine.create_world()
    cid = engine.create_character(world, "Wei")
    engine.db.execute("UPDATE characters SET hunger = 0, thirst = 0, health = 5 WHERE character_id = ?", (cid,))
    engine.tick.advance(world, 10 * 24)
    row = engine.character(cid)
    assert row["alive"] == 0
    assert row["health"] == 0
    assert row["death_cause"] == "starvation and dehydration"
    assert row["death_date"] == "Year 1, Month 1, Day 3, 00:00"
    assert engine.living_characters(world) == []
    engine.tick.advance(world, 24)
    engine.kill_character(cid, "test")
    assert engine.db.one("SELECT COUNT(*) AS count FROM events WHERE character_id = ? AND kind = 'death'", (cid,))["count"] == 1
    engine.db.close()
    reopened = GameEngine.open(path, 42)
    try:
        assert reopened.character(cid)["death_date"] == row["death_date"]
        assert "life has ended" in reopened.perform(cid, "eat")
    finally:
        reopened.db.close()

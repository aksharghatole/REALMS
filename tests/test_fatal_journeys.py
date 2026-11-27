from game.engine import GameEngine


def test_fatal_travel_does_not_arrive(tmp_path):
    engine = GameEngine.open(tmp_path / "fatal.db", 42)
    try:
        world = engine.create_world()
        cid = engine.create_character(world, "Wei")
        origin = engine.character(cid)["location_id"]
        engine.db.execute("UPDATE characters SET health = 1, thirst = 0 WHERE character_id = ?", (cid,))
        result = engine.perform(cid, "travel to Eastern Market")
        row = engine.character(cid)
        assert not row["alive"]
        assert row["location_id"] == origin
        assert "life ended" in result
        assert "arrive" not in result
        journey = engine.db.one("SELECT status FROM journeys WHERE traveler_id = ?", (cid,))
        assert journey["status"] == "CANCELLED"
        assert engine.db.one("SELECT COUNT(*) AS n FROM events WHERE character_id = ? AND kind = 'death'", (cid,))["n"] == 1
        engine.tick.advance(world, 24)
        assert engine.character(cid)["location_id"] == origin
    finally:
        engine.db.close()


def test_explicit_death_cancels_planned_and_active_journeys(tmp_path):
    engine = GameEngine.open(tmp_path / "planned.db", 42)
    try:
        world = engine.create_world()
        cid = engine.create_character(world, "Wei")
        planned = engine.plan_journey(cid, "Azure Village", "Eastern Market")
        active = engine.plan_journey(cid, "Azure Village", "Eastern Market")
        engine.depart_journey(active["journey_id"])
        engine.kill_character(cid, "test")
        for journey in (planned, active):
            assert engine.db.one("SELECT status FROM journeys WHERE journey_id = ?", (journey["journey_id"],))["status"] == "CANCELLED"
    finally:
        engine.db.close()

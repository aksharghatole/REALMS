from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from game.engine import GameEngine


def test_exploration_persists_and_creates_travel_routes(tmp_path):
    path = tmp_path / "explore.db"
    engine = GameEngine.open(path, 42)
    world = engine.create_world()
    cid = engine.create_character(world, "Wei")
    origin = engine.character(cid)["location_id"]
    old_routes = {r["destination"] for r in engine.available_routes(cid)}
    start = engine.date(world)
    assert engine.exploration_remaining(cid) == 2
    assert "discover a trail" in engine.perform(cid, "explore")
    assert engine.date(world) == start.advance(6)
    assert engine.character(cid)["fatigue"] == 22
    new_route = next(r for r in engine.available_routes(cid) if r["destination"] not in old_routes)
    name = new_route["destination"]
    assert name in engine.map_text(world, origin)
    assert "discover a trail" in engine.perform(cid, "scout")
    assert engine.exploration_remaining(cid) == 0
    end = engine.date(world)
    assert "No unexplored" in engine.perform(cid, "explore")
    assert engine.date(world) == end
    assert engine.db.one("SELECT COUNT(*) AS n FROM events WHERE world_id = ? AND kind = 'exploration'", (world,))["n"] == 2
    engine.db.close()
    reopened = GameEngine.open(path, 42)
    try:
        assert reopened.exploration_remaining(cid) == 0
        assert name in reopened.map_text(world, origin)
        assert "arrive" in reopened.perform(cid, f"travel to {name}")
        assert reopened.character(cid)["location_id"] != origin
        assert "Azure Village" in {r["destination"] for r in reopened.available_routes(cid)}
    finally:
        reopened.db.close()


def test_exhausted_and_dead_characters_cannot_explore(tmp_path):
    engine = GameEngine.open(tmp_path / "limits.db", 42)
    try:
        world = engine.create_world()
        cid = engine.create_character(world, "Wei")
        engine.db.execute("UPDATE characters SET fatigue = 99 WHERE character_id = ?", (cid,))
        before = engine.date(world)
        assert "exhausted" in engine.perform(cid, "explore")
        assert engine.date(world) == before
        assert engine.exploration_remaining(cid) == 2
        engine.kill_character(cid, "test")
        assert "ended" in engine.perform(cid, "explore")
        assert engine.exploration_remaining(cid) == 0
    finally:
        engine.db.close()


def test_exploration_button_expands_destination_selector(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_DB", tmp_path / "explore-ui.db")
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
        next(b for b in app.button if b.label == "Enter the world").click().run()
        before = next(s for s in app.selectbox if s.label == "Destination").options
        app.button(key="explore-local").click().run()
        assert not app.exception
        after = next(s for s in app.selectbox if s.label == "Destination").options
        assert len(after) == len(before) + 1
        assert any("discover a trail" in x.value for x in app.info)
    finally:
        st.cache_resource.clear()

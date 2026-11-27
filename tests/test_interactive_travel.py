from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from game.actions import Action
from game.engine import GameEngine


def test_routes_are_local_bidirectional_and_affordable(tmp_path):
    engine = GameEngine.open(tmp_path / "routes.db", 42)
    try:
        world = engine.create_world()
        cid = engine.create_character(world, "Wei")
        routes = {r["destination"]: r for r in engine.available_routes(cid)}
        assert set(routes) == {"Eastern Market", "Whispering Forest", "Cloudstep Sect"}
        route = routes["Eastern Market"]
        assert route["distance"] == 3
        start = engine.date(world)
        engine.db.execute("UPDATE characters SET wealth = 0 WHERE character_id = ?", (cid,))
        assert "costs" in engine.perform(cid, Action("travel", "Eastern Market"))
        assert engine.date(world) == start
        engine.db.execute("UPDATE characters SET wealth = 20 WHERE character_id = ?", (cid,))
        assert "arrive" in engine.perform(cid, Action("travel", "Eastern Market"))
        assert engine.character(cid)["wealth"] == 20 - route["travel_cost"]
        assert engine.date(world) == start.advance(72)
        assert [r["destination"] for r in engine.available_routes(cid)] == ["Azure Village"]
        assert "safe route" in engine.perform(cid, Action("travel", "Cloudstep Sect"))
        assert "arrive" in engine.perform(cid, Action("travel", "Azure Village"))
        assert set(r["destination"] for r in engine.available_routes(cid)) == set(routes)
    finally:
        engine.db.close()


def test_travel_selector_updates_location(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_DB", tmp_path / "travel-ui.db")
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
        next(b for b in app.button if b.label == "Enter the world").click().run()
        assert not app.exception
        selector = next(s for s in app.selectbox if s.label == "Destination")
        selector.set_value("Eastern Market")
        app.button(key="travel-go").click().run()
        assert not app.exception
        assert any("Eastern Market" in h.value and "Day 4" in h.value for h in app.subheader)
        assert next(s for s in app.selectbox if s.label == "Destination").options == ["Azure Village"]
    finally:
        st.cache_resource.clear()

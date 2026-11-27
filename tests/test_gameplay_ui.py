from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from game.engine import GameEngine


def button(app, label):
    return next(item for item in app.button if item.label == label)


def text_input(app, label):
    return next(item for item in app.text_input if item.label == label)


def test_character_name_validation(tmp_path):
    engine = GameEngine.open(tmp_path / "names.db", 42)
    try:
        world = engine.create_world()
        with pytest.raises(ValueError, match="name cannot be empty"):
            engine.create_character(world, "   ")
        assert engine.living_characters(world) == []
        cid = engine.create_character(world, "  Wei  ")
        assert engine.character(cid)["name"] == "Wei"
    finally:
        engine.db.connection.close()


def test_player_can_create_act_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_DB", tmp_path / "ui.db")
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
        assert not app.exception
        text_input(app, "Name").set_value("  ")
        button(app, "Enter the world").click().run()
        assert not app.exception
        assert any("name cannot be empty" in item.value for item in app.error)
        text_input(app, "Name").set_value("Wei")
        button(app, "Enter the world").click().run()
        assert not app.exception
        assert button(app, "Confirm permanent death").disabled
        text_input(app, "What do you do?").set_value("work for 5 days")
        button(app, "Act").click().run()
        assert not app.exception
        assert next(item.value for item in app.metric if item.label == "Wealth") == "30"
        assert any("Day 6" in item.value for item in app.subheader)
        assert app.info
        button(app, "Return to character selection").click().run()
        assert not app.exception
        button(app, "Resume character").click().run()
        assert not app.exception
        assert next(item.value for item in app.metric if item.label == "Wealth") == "30"
    finally:
        st.cache_resource.clear()

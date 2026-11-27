from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config


def test_daily_life_controls_consume_supplies(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_DB", tmp_path / "daily.db")
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
        next(b for b in app.button if b.label == "Enter the world").click().run()
        assert not app.exception
        assert app.table
        app.button(key="daily-eat").click().run()
        assert not app.exception
        assert app.button(key="daily-eat").label == "Eat food (4)"
        assert app.button(key="daily-eat").disabled
        app.button(key="daily-drink").click().run()
        assert not app.exception
        assert app.button(key="daily-drink").label == "Drink water (4)"
        assert app.button(key="daily-drink").disabled
        app.button(key="daily-rest").click().run()
        assert not app.exception
        assert any("16:00" in x.value for x in app.subheader)
    finally:
        st.cache_resource.clear()

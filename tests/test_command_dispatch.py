import pytest

from game.engine import GameEngine


@pytest.fixture
def game(tmp_path):
    engine = GameEngine.open(tmp_path / "commands.db", 42)
    world = engine.create_world()
    character = engine.create_character(world, "Wei")
    yield engine, world, character
    engine.db.connection.close()


def test_save_command_persists_without_advancing_time(game):
    engine, world, character = game
    before = engine.date(world)
    assert engine.perform(character, "save") == "World saved."
    assert engine.latest_save() == (world, character)
    assert engine.date(world) == before


def test_breakthrough_command_dispatches_to_breakthrough(game, monkeypatch):
    engine, world, character = game
    calls = []
    monkeypatch.setattr(engine, "attempt_breakthrough", lambda cid: calls.append(cid) or "Breakthrough attempted.")
    before = engine.date(world)
    assert engine.perform(character, "attempt breakthrough") == "Breakthrough attempted."
    assert calls == [character]
    assert engine.date(world) == before


@pytest.mark.parametrize("command", ["travel", "join", "leave", "buy", "sell"])
def test_missing_target_does_not_advance_time_or_change_character(game, command):
    engine, world, character = game
    before = engine.date(world)
    state = dict(engine.character(character))
    assert "Specify a target" in engine.perform(character, command)
    assert engine.date(world) == before
    assert dict(engine.character(character)) == state

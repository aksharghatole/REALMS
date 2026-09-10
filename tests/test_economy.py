import tempfile

from game.database.db import Database
from game.engine import GameEngine


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_market_prices_and_traceable_transactions():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")

    market = engine.market_for_location(world, "Azure Village")
    grain = engine.market_price(world, market["market_id"], "grain")
    assert grain["unit_price"] > 0

    before = engine.character(character)["wealth"]
    result = engine.buy_item(character, "grain", 1)
    assert result["quantity"] == 1
    assert engine.character(character)["wealth"] < before
    transaction = db.one("SELECT * FROM trade_transactions WHERE transaction_id = ?", (result["transaction_id"],))
    assert transaction["total_value"] == transaction["unit_price"] * transaction["quantity"]
    assert db.one("SELECT quantity FROM inventories WHERE character_id = ? AND item = 'Food'", (character,))["quantity"] >= 6
    handle.close()


def test_supply_demand_changes_price_deterministically():
    handle, _, engine, world = make_engine()
    market = engine.market_for_location(world, "Azure Village")
    before = engine.market_price(world, market["market_id"], "grain")["unit_price"]
    engine.adjust_market_supply(world, market["market_id"], "grain", -80, 120)
    after = engine.market_price(world, market["market_id"], "grain")["unit_price"]
    assert after > before
    handle.close()


def test_bank_loan_repayment_and_default_are_persistent():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Lin")
    bank = engine.create_bank(world, "Azure Merchant Bank", "Azure Village", capital=1000)
    loan = engine.issue_loan(character, bank["bank_id"], 10, interest_rate=0.1, term_days=30)
    assert engine.character(character)["wealth"] == 30
    engine.repay_loan(character, loan["loan_id"], 5)
    remaining = db.one("SELECT remaining_balance FROM loans WHERE loan_id = ?", (loan["loan_id"],))["remaining_balance"]
    assert remaining == 6
    handle.close()


def test_economic_tick_is_stable_and_old_trade_api_works():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Cai")
    assert "buy" in engine.perform(character, "buy rice")
    engine.simulate_economy(world, 30)
    assert db.one("SELECT COUNT(*) AS count FROM market_prices WHERE world_id = ?", (world,))["count"] > 0
    assert db.one("SELECT COUNT(*) AS count FROM trade_transactions WHERE world_id = ?", (world,))["count"] >= 1
    handle.close()

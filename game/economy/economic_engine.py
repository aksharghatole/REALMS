from __future__ import annotations

import uuid
from typing import Callable


DEFAULT_GOODS = {
    "grain": (3, 100, 80),
    "iron": (8, 60, 45),
    "wood": (2, 90, 70),
    "herbs": (5, 45, 35),
    "food": (3, 100, 80),
    "water": (1, 100, 80),
}


class EconomicEngine:
    """Deterministic, persistent economy service layered over the existing DB."""

    def __init__(self, db, date: Callable[[str], object], log: Callable[..., None] | None = None):
        self.db = db
        self.date = date
        self.log = log

    def ensure_currency(self, world_id: str, name: str = "Azure Coin") -> dict:
        row = self.db.one("SELECT * FROM currencies WHERE world_id = ? AND name = ?", (world_id, name))
        if row:
            return dict(row)
        currency_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO currencies (currency_id, world_id, name, symbol, issuing_authority, region, stability, supply, reserve, exchange_rate, inflation, confidence, convertibility, legality) VALUES (?, ?, ?, ?, ?, ?, 80, 0, 0, 100, 0, 80, 100, 'legal')",
            (currency_id, world_id, name, "AC", "local government", "local"),
        )
        return dict(self.db.one("SELECT * FROM currencies WHERE currency_id = ?", (currency_id,)))

    def market_for_location(self, world_id: str, location_name: str) -> dict:
        location = self.db.one("SELECT location_id FROM locations WHERE world_id = ? AND name = ?", (world_id, location_name))
        market = self.db.one("SELECT * FROM markets WHERE world_id = ? AND name = ?", (world_id, location_name))
        if market:
            return dict(market)
        market_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO markets (market_id, world_id, location_id, name, market_type, wealth, confidence, last_day) VALUES (?, ?, ?, ?, 'local', 1000, 70, ?)",
            (market_id, world_id, location["location_id"] if location else None, location_name, self.date(world_id).day_of_year),
        )
        for good, (base_value, supply, demand) in DEFAULT_GOODS.items():
            self._ensure_price(world_id, market_id, good, base_value, supply, demand)
        return dict(self.db.one("SELECT * FROM markets WHERE market_id = ?", (market_id,)))

    def _ensure_price(self, world_id: str, market_id: str, good: str, base_value: int, supply: int, demand: int) -> dict:
        row = self.db.one("SELECT * FROM market_prices WHERE market_id = ? AND good = ?", (market_id, good))
        if row:
            return dict(row)
        price_id = str(uuid.uuid4())
        unit_price = max(1, round(base_value * (1 + max(0, min(3.0, (demand - supply) / max(1, supply))))))
        self.db.execute(
            "INSERT INTO market_prices (market_price_id, world_id, market_id, good, base_value, supply, demand, stockpile, unit_price, production_cost, scarcity, seasonality, updated_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (price_id, world_id, market_id, good, base_value, supply, demand, supply, unit_price, max(1, base_value // 2), self._scarcity(supply, demand), self.date(world_id).day_of_year),
        )
        self.db.execute("INSERT OR IGNORE INTO market_inventory (market_id, good, quantity) VALUES (?, ?, ?)", (market_id, good, supply))
        return dict(self.db.one("SELECT * FROM market_prices WHERE market_price_id = ?", (price_id,)))

    @staticmethod
    def _scarcity(supply: int, demand: int) -> int:
        if demand <= supply:
            return 0
        return min(100, (demand - supply) * 100 // max(1, demand))

    def market_price(self, world_id: str, market_id: str, good: str) -> dict:
        key = good.lower().strip()
        if key == "rice":
            key = "grain"
        row = self.db.one("SELECT * FROM market_prices WHERE market_id = ? AND good = ?", (market_id, key))
        if row:
            return dict(row)
        base, supply, demand = DEFAULT_GOODS.get(key, (5, 50, 40))
        return self._ensure_price(world_id, market_id, key, base, supply, demand)

    def adjust_market_supply(self, world_id: str, market_id: str, good: str, supply_delta: int, demand_delta: int = 0) -> dict:
        price = self.market_price(world_id, market_id, good)
        supply = max(0, price["supply"] + supply_delta)
        demand = max(0, price["demand"] + demand_delta)
        unit_price = max(1, round(price["base_value"] * (1 + max(0, min(3.0, (demand - supply) / max(1, supply))))))
        self.db.execute(
            "UPDATE market_prices SET supply = ?, demand = ?, stockpile = MAX(0, stockpile + ?), scarcity = ?, unit_price = ?, updated_day = ? WHERE market_price_id = ?",
            (supply, demand, supply_delta, self._scarcity(supply, demand), unit_price, self.date(world_id).day_of_year, price["market_price_id"]),
        )
        self.db.execute("INSERT INTO market_inventory (market_id, good, quantity) VALUES (?, ?, MAX(0, ?)) ON CONFLICT(market_id, good) DO UPDATE SET quantity = MAX(0, quantity + ?)", (market_id, price["good"], supply_delta, supply_delta))
        return self.market_price(world_id, market_id, price["good"])

    def _canonical_good(self, good: str) -> tuple[str, str]:
        key = good.lower().strip()
        if key == "rice":
            return "grain", "Food"
        if key in {"grain", "food"}:
            return "food", "Food"
        if key == "herbs":
            return key, "Herbs"
        if key == "wood":
            return key, "Wood"
        if key == "iron":
            return key, "Iron"
        return key, good.title()

    def buy_item(self, character_id: str, good: str, quantity: int = 1) -> dict:
        if quantity < 1:
            raise ValueError("Quantity must be positive")
        character = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        if character is None:
            raise ValueError("Unknown character")
        location = self.db.one("SELECT name FROM locations WHERE location_id = ?", (character["location_id"],))
        market = self.market_for_location(character["world_id"], location["name"] if location else "local market")
        key, item = self._canonical_good(good)
        price = self.market_price(character["world_id"], market["market_id"], key)
        available = self.db.one("SELECT quantity FROM market_inventory WHERE market_id = ? AND good IN (?, ?)", (market["market_id"], key, "grain" if key == "rice" else key))
        if available is None or available["quantity"] < quantity:
            raise ValueError(f"The market has insufficient {key}.")
        total = price["unit_price"] * quantity
        if character["wealth"] < total:
            raise ValueError(f"You need {total} coins to buy {item.lower()}.")
        currency = self.ensure_currency(character["world_id"])
        transaction_id = str(uuid.uuid4())
        now = self.date(character["world_id"])
        self.db.execute("UPDATE characters SET wealth = wealth - ? WHERE character_id = ? AND wealth >= ?", (total, character_id, total))
        self.adjust_market_supply(character["world_id"], market["market_id"], key, -quantity, 0)
        self.db.execute("INSERT INTO inventories (character_id, item, quantity) VALUES (?, ?, ?) ON CONFLICT(character_id, item) DO UPDATE SET quantity = quantity + excluded.quantity", (character_id, item, quantity))
        self.db.execute("INSERT INTO trade_transactions (transaction_id, world_id, timestamp, buyer_id, seller_id, good, quantity, unit_price, total_value, currency_id, location, reason, tax, fees) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'market purchase', 0, 0)", (transaction_id, character["world_id"], now.text(), character_id, f"market:{market['market_id']}", key, quantity, price["unit_price"], total, currency["currency_id"], market["name"]))
        return {"transaction_id": transaction_id, "quantity": quantity, "unit_price": price["unit_price"], "total_value": total, "good": key}

    def sell_item(self, character_id: str, good: str, quantity: int = 1) -> dict:
        if quantity < 1:
            raise ValueError("Quantity must be positive")
        character = self.db.one("SELECT * FROM characters WHERE character_id = ?", (character_id,))
        if character is None:
            raise ValueError("Unknown character")
        location = self.db.one("SELECT name FROM locations WHERE location_id = ?", (character["location_id"],))
        market = self.market_for_location(character["world_id"], location["name"] if location else "local market")
        key, item = self._canonical_good(good)
        held = self.db.one("SELECT quantity FROM inventories WHERE character_id = ? AND item = ?", (character_id, item))
        if held is None or held["quantity"] < quantity:
            raise ValueError(f"You have no {item.lower()} to sell.")
        price = self.market_price(character["world_id"], market["market_id"], key)
        total = price["unit_price"] * quantity
        currency = self.ensure_currency(character["world_id"])
        transaction_id = str(uuid.uuid4())
        now = self.date(character["world_id"])
        self.db.execute("UPDATE inventories SET quantity = quantity - ? WHERE character_id = ? AND item = ? AND quantity >= ?", (quantity, character_id, item, quantity))
        self.db.execute("UPDATE characters SET wealth = wealth + ? WHERE character_id = ?", (total, character_id))
        self.adjust_market_supply(character["world_id"], market["market_id"], key, quantity, 0)
        self.db.execute("INSERT INTO trade_transactions (transaction_id, world_id, timestamp, buyer_id, seller_id, good, quantity, unit_price, total_value, currency_id, location, reason, tax, fees) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)", (transaction_id, character["world_id"], now.text(), f"market:{market['market_id']}", character_id, key, quantity, price["unit_price"], total, currency["currency_id"], market["name"], "market sale"))
        return {"transaction_id": transaction_id, "quantity": quantity, "unit_price": price["unit_price"], "total_value": total, "good": key}

    def create_bank(self, world_id: str, name: str, location: str, capital: int = 1000) -> dict:
        bank_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO banks (bank_id, world_id, name, location, capital, reserves, deposits, loans_outstanding, interest_rate, reputation, status) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 10, 50, 'active')", (bank_id, world_id, name, location, capital, capital))
        return dict(self.db.one("SELECT * FROM banks WHERE bank_id = ?", (bank_id,)))

    def issue_loan(self, borrower_id: str, bank_id: str, principal: int, interest_rate: int = 10, term_days: int = 30) -> dict:
        if principal <= 0:
            raise ValueError("Loan principal must be positive")
        borrower = self.db.one("SELECT * FROM characters WHERE character_id = ?", (borrower_id,))
        bank = self.db.one("SELECT * FROM banks WHERE bank_id = ? AND status = 'active'", (bank_id,))
        if borrower is None or bank is None or bank["reserves"] < principal:
            raise ValueError("The bank cannot issue this loan.")
        now = self.date(borrower["world_id"])
        rate_percent = interest_rate * 100 if isinstance(interest_rate, float) and interest_rate < 1 else interest_rate
        total = principal + round(principal * rate_percent / 100)
        loan_id = str(uuid.uuid4())
        self.db.execute("UPDATE characters SET wealth = wealth + ? WHERE character_id = ?", (principal, borrower_id))
        self.db.execute("UPDATE banks SET reserves = reserves - ?, loans_outstanding = loans_outstanding + ? WHERE bank_id = ?", (principal, principal, bank_id))
        self.db.execute("INSERT INTO loans (loan_id, world_id, bank_id, borrower_id, principal, interest_rate, term_days, collateral, default_risk, remaining_balance, status, issued_day, due_day) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, 'active', ?, ?)", (loan_id, borrower["world_id"], bank_id, borrower_id, principal, rate_percent, term_days, min(95, max(5, 50 - borrower["wealth"] // 2)), total, now.day_of_year, now.day_of_year + term_days))
        return dict(self.db.one("SELECT * FROM loans WHERE loan_id = ?", (loan_id,)))

    def repay_loan(self, borrower_id: str, loan_id: str, amount: int) -> dict:
        loan = self.db.one("SELECT * FROM loans WHERE loan_id = ? AND borrower_id = ? AND status = 'active'", (loan_id, borrower_id))
        borrower = self.db.one("SELECT wealth FROM characters WHERE character_id = ?", (borrower_id,))
        if loan is None or borrower is None or amount <= 0 or borrower["wealth"] < amount:
            raise ValueError("Unable to make that loan payment.")
        payment = min(amount, loan["remaining_balance"])
        remaining = loan["remaining_balance"] - payment
        day = self.date(loan["world_id"]).day_of_year
        self.db.execute("UPDATE characters SET wealth = wealth - ? WHERE character_id = ?", (payment, borrower_id))
        self.db.execute("UPDATE loans SET remaining_balance = ?, status = CASE WHEN ? = 0 THEN 'paid' ELSE status END WHERE loan_id = ?", (remaining, remaining, loan_id))
        self.db.execute("UPDATE banks SET reserves = reserves + ?, loans_outstanding = MAX(0, loans_outstanding - ?) WHERE bank_id = ?", (payment, payment, loan["bank_id"]))
        self.db.execute("INSERT INTO loan_payments (payment_id, loan_id, amount, paid_day, remaining_balance) VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), loan_id, payment, day, remaining))
        return dict(self.db.one("SELECT * FROM loans WHERE loan_id = ?", (loan_id,)))

    def simulate(self, world_id: str, days: int = 1) -> dict:
        markets = self.db.all("SELECT * FROM markets WHERE world_id = ?", (world_id,))
        for market in markets:
            for price in self.db.all("SELECT * FROM market_prices WHERE market_id = ?", (market["market_id"],)):
                demand_delta = max(-2, min(2, price["demand"] // 50 - price["supply"] // 60))
                self.adjust_market_supply(world_id, market["market_id"], price["good"], 0, demand_delta)
        current_day = self.date(world_id).day_of_year
        for loan in self.db.all("SELECT * FROM loans WHERE world_id = ? AND status = 'active' AND due_day < ?", (world_id, current_day)):
            self.db.execute("UPDATE loans SET status = 'defaulted', default_risk = MIN(100, default_risk + 20) WHERE loan_id = ?", (loan["loan_id"],))
            self.db.execute("INSERT INTO economic_events (economic_event_id, world_id, kind, text, severity, created_day) VALUES (?, ?, 'banking', ?, 2, ?)", (str(uuid.uuid4()), world_id, f"A loan to {loan['borrower_id']} has defaulted.", current_day))
        return {"markets_updated": len(markets), "days": days}

    def news(self, world_id: str) -> list[dict]:
        return [dict(row) for row in self.db.all("SELECT * FROM economic_news WHERE world_id = ? ORDER BY created_day DESC, rowid DESC LIMIT 10", (world_id,))]

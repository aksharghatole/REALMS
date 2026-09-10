from __future__ import annotations

import math
import uuid


TRANSPORT_SPEEDS = {
    "walking": (1, 1, 0),
    "animal": (2, 2, 10),
    "horse": (3, 1, 12),
    "ox cart": (1, 8, 8),
    "caravan": (2, 20, 15),
    "river boat": (2, 50, 20),
    "sailing ship": (3, 200, 40),
    "railway": (8, 500, 35),
    "aircraft": (24, 100, 100),
    "spirit boat": (12, 100, 80),
    "teleportation": (10_000, 1_000, 500),
}


class TransportEngine:
    """Persistent journeys, cargo, infrastructure, and delayed messages."""

    def __init__(self, db, date):
        self.db = db
        self.date = date

    def serial(self, world_id: str) -> int:
        current = self.date(world_id)
        return (current.year - 1) * 360 + current.day_of_year

    def _route(self, world_id: str, origin: str, destination: str):
        return self.db.one(
            "SELECT * FROM routes WHERE world_id = ? AND ((from_location = ? AND to_location = ?) OR (from_location = ? AND to_location = ?)) LIMIT 1",
            (world_id, origin, destination, destination, origin),
        )

    def _transport(self, name: str) -> tuple[int, int, int]:
        return TRANSPORT_SPEEDS.get(name.lower(), TRANSPORT_SPEEDS["walking"])

    def create_route(self, world_id: str, origin: str, destination: str, distance: int, terrain: str = "road", danger: int = 0, travel_cost: int = 0) -> dict:
        if distance <= 0:
            raise ValueError("Route distance must be positive")
        route_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO routes (route_id, world_id, from_location, to_location, distance, terrain, danger, travel_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (route_id, world_id, origin, destination, distance, terrain, max(0, danger), max(0, travel_cost)))
        return dict(self.db.one("SELECT * FROM routes WHERE route_id = ?", (route_id,)))

    def plan_journey(self, traveler_id: str, origin: str, destination: str, transport_type: str = "walking", cargo_id: str | None = None) -> dict:
        traveler = self.db.one("SELECT * FROM characters WHERE character_id = ?", (traveler_id,)) if traveler_id else None
        world_id = traveler["world_id"] if traveler else self.db.one("SELECT world_id FROM cargo WHERE cargo_id = ?", (cargo_id,))["world_id"]
        route = self._route(world_id, origin, destination)
        distance = route["distance"] if route else 1
        speed, _, _ = self._transport(transport_type)
        estimated_hours = max(1, math.ceil(distance * 24 / speed))
        journey_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO journeys (journey_id, world_id, traveler_id, cargo_id, origin, destination, route_id, transport_type, departure_serial, arrival_serial, estimated_hours, progress_hours, current_location, status, danger, created_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, 0, ?, 'PLANNED', ?, ?)",
            (journey_id, world_id, traveler_id, cargo_id, origin, destination, route["route_id"] if route else None, transport_type, estimated_hours, origin, route["danger"] if route else 0, self.serial(world_id)),
        )
        return dict(self.db.one("SELECT * FROM journeys WHERE journey_id = ?", (journey_id,)))

    def depart_journey(self, journey_id: str) -> dict:
        journey = self.db.one("SELECT * FROM journeys WHERE journey_id = ?", (journey_id,))
        if journey is None:
            raise ValueError("Unknown journey")
        if journey["status"] not in {"PLANNED", "DELAYED"}:
            return dict(journey)
        departure = self.serial(journey["world_id"])
        arrival = departure + max(1, math.ceil(journey["estimated_hours"] / 24))
        self.db.execute("UPDATE journeys SET status = 'IN_TRANSIT', departure_serial = ?, arrival_serial = ?, progress_hours = 0 WHERE journey_id = ?", (departure, arrival, journey_id))
        if journey["cargo_id"]:
            self.db.execute("UPDATE cargo SET status = 'IN_TRANSIT' WHERE cargo_id = ?", (journey["cargo_id"],))
        return dict(self.db.one("SELECT * FROM journeys WHERE journey_id = ?", (journey_id,)))

    def create_cargo(self, world_id: str, good: str, quantity: int, origin: str, destination: str, owner_id: str | None = None, value: int = 0) -> dict:
        if quantity <= 0:
            raise ValueError("Cargo quantity must be positive")
        cargo_id = str(uuid.uuid4())
        created = self.serial(world_id)
        self.db.execute("INSERT INTO cargo (cargo_id, world_id, owner_id, good, quantity, origin, destination, value, weight, volume, perishability, created_serial, expiry_serial, security, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 50, 'READY')", (cargo_id, world_id, owner_id, good, quantity, origin, destination, value, quantity, quantity, 0, created))
        return dict(self.db.one("SELECT * FROM cargo WHERE cargo_id = ?", (cargo_id,)))

    def plan_cargo_journey(self, cargo_id: str, transport_type: str = "walking") -> dict:
        cargo = self.db.one("SELECT * FROM cargo WHERE cargo_id = ?", (cargo_id,))
        if cargo is None:
            raise ValueError("Unknown cargo")
        return self.plan_journey(None, cargo["origin"], cargo["destination"], transport_type, cargo_id)

    def create_warehouse(self, world_id: str, name: str, location: str, capacity: int = 100, owner_id: str | None = None) -> dict:
        if capacity <= 0:
            raise ValueError("Warehouse capacity must be positive")
        warehouse_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO warehouses (warehouse_id, world_id, name, location, owner_id, capacity, used_capacity, security, condition, operating_cost, status) VALUES (?, ?, ?, ?, ?, ?, 0, 50, 100, 0, 'active')", (warehouse_id, world_id, name, location, owner_id, capacity))
        return dict(self.db.one("SELECT * FROM warehouses WHERE warehouse_id = ?", (warehouse_id,)))

    def create_infrastructure(self, world_id: str, name: str, kind: str, location: str, condition: int = 100, owner_id: str | None = None) -> dict:
        infrastructure_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO infrastructure (infrastructure_id, world_id, name, kind, owner_id, builder_id, construction_date, location, capacity, condition, maintenance_cost, operating_cost, technology_level, status) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 10, ?, 0, 0, 0, 'active')", (infrastructure_id, world_id, name, kind, owner_id, self.date(world_id).text(), location, max(0, min(100, condition))))
        return dict(self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,)))

    def maintain_infrastructure(self, infrastructure_id: str, days: int = 1) -> dict:
        row = self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,))
        if row is None:
            raise ValueError("Unknown infrastructure")
        condition = max(0, row["condition"] - max(0, days) // 10)
        self.db.execute("UPDATE infrastructure SET condition = ? WHERE infrastructure_id = ?", (condition, infrastructure_id))
        return dict(self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,)))

    def repair_infrastructure(self, infrastructure_id: str, amount: int = 10) -> dict:
        row = self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,))
        if row is None:
            raise ValueError("Unknown infrastructure")
        self.db.execute("UPDATE infrastructure SET condition = MIN(100, condition + ?) WHERE infrastructure_id = ?", (max(0, amount), infrastructure_id))
        return dict(self.db.one("SELECT * FROM infrastructure WHERE infrastructure_id = ?", (infrastructure_id,)))

    def send_message(self, sender_id: str, receiver_id: str, content: str, method: str = "courier", secrecy: str = "PRIVATE") -> dict:
        sender = self.db.one("SELECT * FROM characters WHERE character_id = ?", (sender_id,))
        receiver = self.db.one("SELECT * FROM characters WHERE character_id = ?", (receiver_id,))
        if sender is None or receiver is None or sender["world_id"] != receiver["world_id"]:
            raise ValueError("Sender and receiver must exist in the same world")
        latency = {"face-to-face": 0, "messenger": 12, "courier": 24, "letter": 48, "telegraph": 2, "radio": 1, "magical": 1}.get(method.lower(), 48)
        delivery = self.serial(sender["world_id"]) + max(0, math.ceil(latency / 24))
        message_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO messages (message_id, world_id, sender_id, receiver_id, creation_serial, send_serial, delivery_serial, content, communication_method, route, status, secrecy, reliability) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'IN_TRANSIT', ?, 80)", (message_id, sender["world_id"], sender_id, receiver_id, self.serial(sender["world_id"]), self.serial(sender["world_id"]), delivery, content, method, secrecy))
        message = dict(self.db.one("SELECT * FROM messages WHERE message_id = ?", (message_id,)))
        message["delivery_hours"] = latency
        return message

    def inbox(self, receiver_id: str) -> list[dict]:
        return [dict(row) for row in self.db.all("SELECT * FROM messages WHERE receiver_id = ? AND status = 'DELIVERED' ORDER BY delivery_serial DESC, rowid DESC", (receiver_id,))]

    def step(self, world_id: str, days: int = 1) -> dict:
        now = self.serial(world_id)
        self.db.execute("UPDATE infrastructure SET condition = MAX(0, condition - ?) WHERE world_id = ? AND status = 'active'", (max(0, days // 30), world_id))
        arrived = 0
        for journey in self.db.all("SELECT * FROM journeys WHERE world_id = ? AND status = 'IN_TRANSIT' AND arrival_serial <= ?", (world_id, now)):
            self.db.execute("UPDATE journeys SET status = 'ARRIVED', progress_hours = estimated_hours, current_location = ? WHERE journey_id = ?", (journey["destination"], journey["journey_id"]))
            if journey["traveler_id"]:
                destination = self.db.one("SELECT location_id FROM locations WHERE world_id = ? AND name = ?", (world_id, journey["destination"]))
                if destination:
                    self.db.execute("UPDATE characters SET location_id = ? WHERE character_id = ?", (destination["location_id"], journey["traveler_id"]))
            if journey["cargo_id"]:
                self.db.execute("UPDATE cargo SET status = 'DELIVERED' WHERE cargo_id = ?", (journey["cargo_id"],))
            arrived += 1
        self.db.execute("UPDATE journeys SET progress_hours = MIN(estimated_hours, progress_hours + ?) WHERE world_id = ? AND status = 'IN_TRANSIT'", (max(1, days * 24), world_id))
        delivered = self.db.execute("UPDATE messages SET status = 'DELIVERED' WHERE world_id = ? AND status = 'IN_TRANSIT' AND delivery_serial <= ?", (world_id, now)).rowcount
        return {"journeys_arrived": arrived, "messages_delivered": delivered}

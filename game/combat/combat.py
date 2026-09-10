from dataclasses import dataclass, field
import random


@dataclass
class Combatant:
    name: str
    health: int
    qi: int
    power: int
    stamina: int = 100
    soul: int = 50
    perception: int = 30
    position: str = "center"
    morale: int = 70
    injuries: list[str] = field(default_factory=list)
    statuses: dict[str, int] = field(default_factory=dict)


class Combat:
    """Deterministic text combat foundation with intentionally limited information."""

    def __init__(self, player: Combatant, enemy: Combatant, seed: int = 1, terrain: str = "road", weather: str = "Clear", distance: int = 6, visibility: int = 80):
        self.player, self.enemy = player, enemy
        self.rng = random.Random(seed)
        self.terrain, self.weather, self.distance, self.visibility = terrain, weather, distance, visibility
        self.round = 0
        self.finished = False

    @property
    def state(self) -> dict:
        return {"round": self.round, "distance": self.distance, "terrain": self.terrain, "weather": self.weather, "visibility": self.visibility, "player": self.player, "enemy": self.enemy}

    def act(self, action: str) -> str:
        action = action.lower().strip()
        self.round += 1
        if action in {"flee", "retreat", "run"}:
            chance = self.player.stamina + self.distance * 3 - self.enemy.perception
            if chance > 45:
                self.finished = True
                return "You break line of sight and escape the fight."
            return "You try to escape, but the enemy cuts off your route."
        if action in {"defend", "dodge"}:
            self.player.stamina = min(100, self.player.stamina + 8)
            self.player.statuses["guarded"] = 1
            return self._enemy_exchange("You take a guarded stance and wait for an opening.")
        if action in {"observe", "study", "watch"}:
            if self.player.perception + self.player.soul // 5 + self.rng.randint(0, 30) > 70:
                return "You notice the enemy favors one side and their breathing is uneven."
            return "Something in the enemy's movement feels wrong, but you cannot yet read it."
        if action in {"move", "behind the tree", "circle"}:
            self.distance = max(1, self.distance + self.rng.choice((-2, -1, 1, 2)))
            self.player.position = "cover" if self.terrain in {"forest", "ruins"} else "flank"
            return self._enemy_exchange(f"You reposition through the {self.terrain}; distance is now {self.distance} meters.")
        if action in {"negotiate", "talk", "intimidate"}:
            if action == "intimidate" and self.player.power + self.player.morale > self.enemy.power + self.enemy.morale:
                self.finished = True
                return "Your threat breaks the enemy's resolve. They lower their weapon."
            return "Words cross the distance, but neither side has yielded."
        damage = max(1, self.player.power + self.player.qi // 10 + self.rng.randint(-3, 3))
        if action in {"feint", "counter"}:
            damage += 3
        if action in {"technique", "dao", "sword dao"}:
            damage += 6
            self.player.stamina = max(0, self.player.stamina - 12)
        if self.player.position == "cover":
            damage += 2
        self.enemy.health = max(0, self.enemy.health - damage)
        if self.enemy.health == 0:
            self.finished = True
            return f"Your {action} lands decisively. {self.enemy.name} falls."
        self.enemy.morale = max(0, self.enemy.morale - damage // 3)
        if damage >= 12:
            self.enemy.injuries.append("deep cut")
            self.enemy.statuses["bleeding"] = 2
        return self._enemy_exchange(f"Your {action} finds an opening and deals {damage} damage.")

    def _enemy_exchange(self, opening: str) -> str:
        if self.finished:
            return opening
        if self.enemy.statuses.get("bleeding", 0):
            self.enemy.statuses["bleeding"] -= 1
            self.enemy.health = max(0, self.enemy.health - 2)
        retaliation = max(1, self.enemy.power + self.rng.randint(-2, 2))
        if self.player.statuses.pop("guarded", 0):
            retaliation //= 2
        self.player.health = max(0, self.player.health - retaliation)
        if self.player.health == 0:
            self.finished = True
            return f"{opening} The counterstrike overwhelms you."
        return f"{opening} The enemy answers; you lose {retaliation} health."

    def visible_enemy(self) -> str:
        condition = "steady"
        if self.enemy.health < 35:
            condition = "badly wounded"
        elif self.enemy.health < 70:
            condition = "hurt"
        detail = "Their movements are difficult to read."
        if self.player.perception >= 70:
            detail = f"Their condition appears {condition}; their stance is {self.enemy.position}."
        return f"{self.enemy.name} stands {self.distance} meters away. {detail}"
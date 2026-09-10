import random
from dataclasses import dataclass

REALMS = [
    "Body Tempering", "Blood Refinement", "Meridian Opening", "Qi Gathering", "Qi Condensation",
    "Spirit Gathering", "Foundation Establishment", "Golden Core", "Nascent Soul", "Soul Formation",
    "Spirit Severing", "Dao Seeking", "Dao Seed", "Dao Palace", "Dao Lord", "Heavenly Transformation",
    "Void Refinement", "Void Integration", "Void Crossing", "Great Ascension", "Immortal Tribulation",
    "Human Immortal", "Earth Immortal", "Heaven Immortal", "Golden Immortal", "Immortal Lord",
    "Immortal King", "Immortal Emperor", "Half-Step Saint", "Saint", "Saint King", "Great Saint",
    "Saint Emperor", "Dao Ancestor", "Dao Sovereign", "Dao Emperor", "Primordial Immortal",
    "Chaos Immortal", "Chaos Lord", "Chaos King", "Chaos Emperor", "Origin Immortal", "Origin Lord",
    "Origin King", "Origin Emperor", "Eternal Immortal", "Eternal Lord", "Eternal King",
    "Eternal Emperor", "Transcendent",
]
STAGES = ("Early", "Middle", "Late", "Peak", "Perfection")
STAGE_COUNTS = (5, 5, 5, 5, 5)


def realm_progression(realm_index: int, internal_structure: tuple[int, ...] | None = None) -> tuple[str, ...]:
    """Return canonical internal stage names for a realm, allowing future expansion."""
    if internal_structure is None:
        internal_structure = STAGE_COUNTS
    if realm_index < 0:
        realm_index = 0
    count = internal_structure[realm_index % len(internal_structure)]
    stages = ("Early", "Middle", "Late", "Peak", "Perfection")
    return tuple(stages[index] for index in range(min(count, len(stages))))


@dataclass(frozen=True)
class CombatPowerProfile:
    realm: int = 0
    internal_level: int = 0
    foundation: int = 0
    body: int = 0
    qi: int = 0
    soul: int = 0
    dao: int = 0
    techniques: int = 0
    artifacts: int = 0
    experience: int = 0
    injuries: float = 0.0
    environment: float = 1.0
    bloodline: float = 1.0
    physique: float = 1.0
    mental_state: float = 1.0

    def total(self) -> float:
        realm_scalar = 1.0 + max(0, self.realm) * 0.22
        internal_scalar = 1.0 + max(0, self.internal_level) * 0.38
        base = (
            self.foundation * 0.9
            + self.body * 1.2
            + self.qi * 0.95
            + self.soul * 0.9
            + self.dao * 1.1
            + self.techniques * 0.8
            + self.artifacts * 0.7
            + self.experience * 0.6
        )
        injury_penalty = max(0.0, self.injuries)
        return (base * realm_scalar * internal_scalar * self.environment * self.bloodline * self.physique * self.mental_state) * (1.0 - injury_penalty)


def realm_name(level: int, stage: int = 0) -> str:
    realm_index = max(0, min(level, len(REALMS) - 1))
    stage_name = STAGES[max(0, min(stage, len(STAGES) - 1))]
    return f"{REALMS[realm_index]} ({stage_name})"


def realm_power(level: int, stage: int = 0) -> int:
    """A baseline only; combat adds body, Dao, technique, and injury modifiers."""
    realm_index = max(0, level)
    stage_index = max(0, min(stage, 4))
    return int((realm_index + 1) * 100 + stage_index * 12)


def breakthrough(stats: dict[str, int], rng: random.Random) -> tuple[bool, str, int]:
    score = stats.get("foundation", 0) + stats.get("comprehension", 0) + stats.get("willpower", 0) + stats.get("qi", 0) + stats.get("soul", 0) - stats.get("karma", 0)
    chance = max(5, min(95, score // 4))
    roll = rng.randint(1, 100)
    if roll > chance:
        return False, "Failed", chance
    quality = "Ordinary" if roll > chance - 20 else "Good" if roll > chance - 40 else "Excellent"
    return True, quality, chance
import random
import uuid
from typing import Any

DEFAULT_SPECIES = {
    "name": "Human",
    "classification": "humanoid",
    "parent_species": None,
    "origin": "Azure Heaven",
    "biological_traits": {
        "height": 1.0,
        "body_mass": 1.0,
        "strength": 1.0,
        "endurance": 1.0,
        "speed": 1.0,
        "reflexes": 1.0,
        "intelligence": 1.0,
        "perception": 1.0,
        "lifespan": 1.0,
        "fertility": 1.0,
        "growth_rate": 1.0,
        "regeneration": 0.4,
        "disease_resistance": 0.5,
        "environmental_tolerance": 1.0,
        "temperature_tolerance": 1.0,
        "oxygen_tolerance": 1.0,
        "radiation_tolerance": 0.5,
        "spiritual_sensitivity": 0.5,
        "qi_affinity": 0.5,
        "soul_resilience": 0.8,
    },
    "average_lifespan": 80,
    "maturity_age": 18,
    "reproduction_model": "sexual",
    "environmental_preferences": ["temperate plains", "settled villages"],
    "physical_capabilities": ["balanced movement", "adaptable body"],
    "intelligence_range": [0, 100],
    "cultivation_affinity": "balanced",
    "technological_affinity": "moderate",
    "population": 1,
    "rarity": "common",
    "extinction_status": "living",
}


def default_species_record(name: str = "Human", **overrides: Any) -> dict[str, Any]:
    record = dict(DEFAULT_SPECIES)
    record["name"] = name
    for key, value in overrides.items():
        if key == "biological_traits":
            record[key] = {**record.get(key, {}), **(value or {})}
        else:
            record[key] = value
    return record


def phenotype_from_genotype(genotype: dict[str, Any], species: dict[str, Any] | None = None) -> dict[str, Any]:
    species_traits = (species or {}).get("biological_traits", {})
    phenotype = {}
    for key, value in {**species_traits, **(genotype or {})}.items():
        if isinstance(value, (int, float)):
            phenotype[key] = float(value)
        else:
            phenotype[key] = value
    return phenotype


def mutation_effect(name: str, rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    effects = {
        "enhanced_lung_capacity": {"strength": 2, "effect": "The lungs hold more breath and the body tolerates thinner air."},
        "stronger_bones": {"strength": 3, "effect": "The skeleton becomes denser and sturdier."},
        "spiritual_sensitivity": {"spiritual_sensitivity": 3, "effect": "The soul resonates with spiritual phenomena more readily."},
        "reduced_fertility": {"fertility": -2, "effect": "The body has a lower fertility rate."},
        "reduced_lifespan": {"lifespan": -2, "effect": "The body ages more quickly than usual."},
    }
    effect = effects.get(name, {"effect": "A subtle biological quirk appears."})
    return {"mutation_id": str(uuid.uuid4()), "name": name, "effect": effect["effect"], "modifiers": {k: v for k, v in effect.items() if k != "effect"}}


def inherit_traits_for_new_character(parent_a: dict[str, Any] | None, parent_b: dict[str, Any] | None, species_name: str = "Human", rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    combined = {}
    parents = [parent_a or {}, parent_b or {}]
    for key in sorted({key for parent in parents for key in parent.keys()}):
        values = [parent.get(key) for parent in parents if key in parent and isinstance(parent.get(key), (int, float))]
        if not values:
            continue
        value = sum(values) / len(values)
        if rng.random() < 0.12:
            value += rng.uniform(-1.5, 1.5)
        combined[key] = round(value, 2)
    if not combined:
        combined = {"strength": 8, "endurance": 8, "spiritual_sensitivity": 4, "fertility": 6, "lifespan": 1.0}
    if species_name.lower().startswith("dragon"):
        combined.setdefault("strength", 12)
        combined.setdefault("lifespan", 2.0)
    if species_name.lower().startswith("spirit"):
        combined.setdefault("spiritual_sensitivity", 12)
    combined.setdefault("species", species_name)
    return combined

from game.engine import GameEngine
from game.database.db import Database
import tempfile


def build_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_species_creation_inheritance_bloodline_and_mutation():
    handle, db, engine, world = build_engine()

    species = engine.create_species(
        "Azure Human",
        classification="humanoid",
        parent_species="Human",
        origin="Azure Heaven",
        average_lifespan=180,
        cultivation_affinity="balanced",
    )
    assert species["name"] == "Azure Human"
    assert engine.species_for_character(engine.create_character(world, "Aiko", species="Azure Human"))["name"] == "Azure Human"

    bloodline = engine.create_bloodline("Sunfire Lineage", "Azure Human", "fire", "strong")
    assert bloodline["name"] == "Sunfire Lineage"

    character = engine.create_character(world, "Ren", species="Azure Human")
    engine.assign_bloodline(character, bloodline["bloodline_id"], expression="dormant")
    inherited = engine.inherit_traits_for_new_character(
        {"strength": 13, "endurance": 8, "spiritual_sensitivity": 7},
        {"strength": 10, "endurance": 12, "spiritual_sensitivity": 9},
        species_name="Azure Human",
    )
    assert inherited["strength"] > 0
    assert inherited["endurance"] > 0

    mutation = engine.mutate_character(character, "enhanced_lung_capacity")
    assert mutation["mutation_id"]
    assert mutation["effect"]

    assert db.one("SELECT COUNT(*) AS count FROM species WHERE name = ?", ("Azure Human",))["count"] == 1
    assert db.one("SELECT COUNT(*) AS count FROM bloodlines WHERE name = ?", ("Sunfire Lineage",))["count"] == 1

    handle.close()


def test_species_defaults_and_population_tracking():
    handle, db, engine, world = build_engine()
    character = engine.create_character(world, "Ming")
    species = engine.species_for_character(character)
    assert species["name"] in {"Human", "Azure Human"}
    assert engine.record_population_change("Human", 8)
    assert db.one("SELECT population FROM species WHERE name = ?", (species["name"],))["population"] >= 1
    handle.close()

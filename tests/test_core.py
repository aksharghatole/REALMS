import tempfile

from game.combat.combat import Combat, Combatant
from game.database.db import Database
from game.engine import GameEngine
from game.ai.provider import FallbackAIProvider


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix=".db")
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_world_and_character_persist():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    assert db.one("SELECT name FROM worlds WHERE world_id = ?", (world,))["name"] == "Azure Heaven"
    assert db.one("SELECT name FROM characters WHERE character_id = ?", (character,))["name"] == "Wei"
    assert db.one("SELECT COUNT(*) AS count FROM npcs WHERE world_id = ?", (world,))["count"] == 7
    handle.close()


def test_actions_advance_time_and_pay():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    engine.perform(character, "work for 5 days")
    assert engine.date(world).day == 6
    assert engine.character(character)["wealth"] == 30
    handle.close()


def test_breakthrough_and_permanent_death():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    result = engine.attempt_breakthrough(character)
    assert result
    engine.kill_character(character, "a test")
    assert engine.character(character)["alive"] == 0
    assert "test" in engine.character(character)["death_cause"]
    handle.close()


def test_combat_is_deterministic_and_tactical():
    combat = Combat(Combatant("Wei", 100, 20, 12), Combatant("Bandit", 20, 10, 5), seed=4)
    message = combat.act("attack")
    assert "damage" in message
    assert combat.enemy.health < 20


def test_talking_creates_relationship_and_family_persists():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    message = engine.perform(character, "talk to Old Han")
    assert "Old Han" in message
    relationship = engine.relationships(character)[0]
    assert relationship["familiarity"] == 5
    family = engine.family(character)
    assert family["name"] == "The Wei Family"
    assert db.one("SELECT COUNT(*) AS count FROM memories WHERE owner_id = ?", (character,))["count"] == 1
    handle.close()


def test_needs_weather_situations_and_trade():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    before = engine.character(character)
    message = engine.perform(character, "work for 5 days")
    after = engine.character(character)
    assert after["fatigue"] > before["fatigue"]
    assert engine.date(world).season == "Spring"
    assert engine.date(world).weather(engine.seed)
    assert engine.open_situations(character)
    assert "buy" in engine.perform(character, "buy rice")
    assert engine.character(character)["wealth"] == 27
    handle.close()


def test_route_travel_and_journal():
    handle, _, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    message = engine.perform(character, "travel to Eastern Market")
    assert "arrive" in message
    current = engine.character(character)
    assert engine.db.one("SELECT name FROM locations WHERE location_id = ?", (current["location_id"],))["name"] == "Eastern Market"
    assert "events" in engine.journal(character)
    assert "Eastern Market" in engine.map_text(world, current["location_id"])
    handle.close()


def test_grounded_free_form_conversation_persists_and_has_boundaries():
    handle, db, engine, world = make_engine()
    engine.set_ai_provider(FallbackAIProvider())
    character = engine.create_character(world, "Wei")
    npc = engine.nearby_npcs(character)[0]
    response = engine.converse(character, npc["npc_id"], "Who is the strongest person in the northern ruins?")
    assert response
    assert "do not know" in response.lower()
    assert db.one("SELECT COUNT(*) AS count FROM conversation_messages")["count"] == 2
    assert db.one("SELECT COUNT(*) AS count FROM memories WHERE owner_id = ?", (npc["npc_id"],))["count"] == 1
    engine.converse(character, npc["npc_id"], "I promise I will help you.")
    relation = db.one("SELECT trust FROM relationships WHERE source_id = ? AND target_id = ?", (character, npc["npc_id"]))
    assert relation["trust"] >= 4
    handle.close()


def test_deep_cultivation_dao_technique_and_tribulation():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    state_before = engine.cultivation_state(character)
    result = engine.cultivation.cultivate(character, "meditation", 30)
    assert result.progress > 0
    assert engine.study_dao(character, "Sword")
    assert engine.practice_technique(character)
    state_after = engine.cultivation_state(character)
    assert state_after["dao_comprehension"] > state_before["dao_comprehension"]
    tribulation = engine.generate_tribulation(character)
    assert tribulation["type"]
    assert engine.tribulation_warning(character)
    assert db.one("SELECT COUNT(*) AS count FROM techniques")["count"] >= 3
    handle.close()


def test_engine_combat_uses_profile_and_records_outcome():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    npc = engine.nearby_npcs(character)[0]
    combat = engine.start_combat(character, npc["npc_id"])
    assert combat.distance == 6
    assert "meters" in combat.visible_enemy()
    message = engine.combat_action(character, "observe")
    assert message
    handle.close()


def test_world_state_lazy_planet_generation_and_war_creation():
    handle, _, engine, world = make_engine()
    state = engine.world_state(world)
    assert state["world_id"] == world
    planet = engine.ensure_planet(world, "Crimson Moon")
    assert planet["name"] == "Crimson Moon"
    war = engine.create_war(world, "Azure Kingdom", "Cloudstep Sect", "resource dispute")
    assert war["cause"] == "resource dispute"
    news = engine.world_news(world)
    assert isinstance(news, list)
    assert engine.simulate_world(world, days=30)
    handle.close()


def test_phase4_data_driven_realms_methods_physiques_and_combat_power():
    from game.cultivation.realms import REALMS, CombatPowerProfile, realm_progression, realm_power
    from game.cultivation.system import CULTIVATION_METHODS
    from game.cultivation.physiques import PHYSIQUES, bloodline_family

    assert len(REALMS) >= 50
    assert "Body Tempering" in REALMS
    assert "Transcendent" in REALMS
    assert "Early" in realm_progression(0)
    assert CULTIVATION_METHODS["meditation"]["speed"] > 0
    assert any(name in PHYSIQUES for name in ["Mortal Body", "Void Body", "Chaos Body"])
    profile_weak = CombatPowerProfile(realm=10, internal_level=2, foundation=50, body=60, qi=40, soul=30, dao=25, techniques=20, artifacts=10, experience=15, injuries=0.2, environment=1.0, bloodline=0.8, physique=0.9, mental_state=1.0)
    profile_strong = CombatPowerProfile(realm=12, internal_level=3, foundation=70, body=65, qi=55, soul=50, dao=40, techniques=35, artifacts=15, experience=28, injuries=0.0, environment=1.0, bloodline=1.0, physique=1.1, mental_state=1.0)
    assert profile_weak.total() < profile_strong.total()
    assert realm_power(10, 2) > realm_power(8, 2)
    assert bloodline_family("Ancient Dragon") == "beast"


def test_exploration_site_generation_and_discovery_persist():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    site = engine.create_exploration_site(world, "Whispering Cavern", site_type="Natural Cave", region="Whispering Forest")
    discovered = engine.discover_site(character, site["site_id"], "rumor")

    assert site["type"] == "Natural Cave"
    assert discovered["discovered_quality"] in {"RUMORED", "LOCATED", "PARTIALLY EXPLORED"}
    assert db.one("SELECT COUNT(*) AS count FROM exploration_sites WHERE world_id = ?", (world,))["count"] == 1
    handle.close()


def test_exploration_gathering_and_artifact_persistence():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    site = engine.create_exploration_site(world, "Ashen Vault", site_type="Ancient Tomb", region="Whispering Forest")
    engine.discover_site(character, site["site_id"], "travel")
    resource = engine.gather_resources(character, site["site_id"], "herbs")
    artifact = engine.create_artifact(site["site_id"], "Moonsteel Dagger", "weapon", quality="Rare")

    assert resource["quantity"] > 0
    assert artifact["name"] == "Moonsteel Dagger"
    assert db.one("SELECT COUNT(*) AS count FROM artifacts WHERE name = ?", ("Moonsteel Dagger",))["count"] == 1
    handle.close()


def test_life_system_family_marriage_and_births():
    handle, db, engine, world = make_engine()
    a = engine.create_character(world, "Lin")
    b = engine.create_character(world, "Yue")
    marriage = engine.create_marriage(a, b, kind="love")
    child = engine.birth_child(a, b, "Jun")

    assert marriage["status"] == "married"
    assert child["name"] == "Jun"
    assert db.one("SELECT COUNT(*) AS count FROM marriages WHERE world_id = ?", (world,))["count"] == 1
    assert db.one("SELECT COUNT(*) AS count FROM family_members WHERE character_id = ?", (child["character_id"],))["count"] == 1
    handle.close()


def test_technology_discovery_and_civilization_growth():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    tech = engine.register_technology(world, "Iron Smelting", "Metallurgy", "Iron Age", description="Refined extraction and smelting of iron for better tools.")
    project = engine.start_research_project(world, character, "Iron Smelting", institution="Village Workshop")
    engine.advance_civilization(world)
    state = engine.civilization_state(world)

    assert tech["name"] == "Iron Smelting"
    assert project["technology_name"] == "Iron Smelting"
    assert state["technology_level"] >= 1
    assert db.one("SELECT COUNT(*) AS count FROM technologies WHERE world_id = ?", (world,))["count"] >= 1
    handle.close()


def test_infrastructure_and_company_persist():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    company = engine.create_company(world, character, "North Smith Works", "Manufacturing")
    infrastructure = engine.build_infrastructure(world, "Market Road", "transport", "Azure Village", owner_id=character)

    assert company["name"] == "North Smith Works"
    assert infrastructure["name"] == "Market Road"
    assert db.one("SELECT COUNT(*) AS count FROM companies WHERE world_id = ?", (world,))["count"] == 1
    handle.close()


def test_life_system_profession_skills_business_and_property():
    handle, db, engine, world = make_engine()
    character = engine.create_character(world, "Wei")
    engine.assign_profession(character, "Blacksmith", "Azure Forge")
    engine.train_skill(character, "smithing", 3)
    business = engine.create_business(character, "Wei Forge", "workshop", "Azure Village", capital=120)
    property_row = engine.buy_property(character, "Lowland Workshop", "workshop", "Azure Village", value=180)

    assert db.one("SELECT profession FROM character_professions WHERE character_id = ?", (character,))["profession"] == "Blacksmith"
    assert db.one("SELECT level FROM skills WHERE character_id = ? AND name = ?", (character, "smithing"))["level"] >= 3
    assert business["owner_id"] == character
    assert property_row["owner_id"] == character
    assert property_row["status"] == "owned"
    handle.close()
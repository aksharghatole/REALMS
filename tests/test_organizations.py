from game.engine import GameEngine
from game.database.db import Database
import tempfile


def make_engine():
    handle = tempfile.NamedTemporaryFile(suffix='.db')
    db = Database(handle.name)
    engine = GameEngine(db, 42)
    world = engine.create_world()
    return handle, db, engine, world


def test_organization_creation_membership_and_roles():
    handle, db, engine, world = make_engine()
    founder = engine.create_character(world, "Zhao")
    guild = engine.create_organization(world, "Silver Crane Guild", "guild", founder)
    member = engine.create_character(world, "Lin")

    membership = engine.join_organization(member, guild["organization_id"], rank="Member", role="Treasurer")
    assert membership["rank"] == "Member"
    assert membership["role"] == "Treasurer"
    assert engine.organization_member(member, guild["organization_id"])["role"] == "Treasurer"
    engine.promote_member(member, guild["organization_id"], "Senior Member")
    engine.assign_role(member, guild["organization_id"], "Secretary", permissions="read,write")
    assert engine.organization_member(member, guild["organization_id"])["rank"] == "Senior Member"
    assert engine.organization_member(member, guild["organization_id"])["role"] == "Secretary"
    assert engine.can_perform(member, guild["organization_id"], "review_finances")
    handle.close()


def test_organization_leadership_succession_and_history():
    handle, db, engine, world = make_engine()
    founder = engine.create_character(world, "Ming")
    heir = engine.create_character(world, "Ming Jr")
    guild = engine.create_organization(world, "Blazing Banner", "guild", founder)
    engine.join_organization(founder, guild["organization_id"], rank="Guildmaster", role="Founder")
    engine.join_organization(heir, guild["organization_id"], rank="Officer", role="Apprentice")
    engine.set_leader(guild["organization_id"], founder)
    assert engine.organization(guild["organization_id"])["leader_id"] == founder
    engine.set_succession(guild["organization_id"], heir, "heir")
    engine.record_organization_event(guild["organization_id"], "leadership", "The guild heir was named in the charter.")
    assert engine.organization_events(guild["organization_id"])[0]["text"]
    assert engine.organization(guild["organization_id"])["succession_rules"] == "heir"
    handle.close()


def test_natural_language_org_commands_parse_and_act():
    handle, _, engine, world = make_engine()
    founder = engine.create_character(world, "Cai")
    org = engine.create_organization(world, "Moonwell School", "school", founder)
    student = engine.create_character(world, "Han")
    joined = engine.perform(student, f"join {org['name']}")
    assert "joined" in joined.lower()
    left = engine.perform(student, f"leave {org['name']}")
    assert "left" in left.lower()
    handle.close()

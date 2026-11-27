import streamlit as st

from config import DEFAULT_DB, DEFAULT_WORLD_SEED
from game.engine import GameEngine
from game.actions import Action
from game.ai.provider import provider_for_mode
from game.cultivation.realms import realm_name


st.set_page_config(page_title="Eternal Realms", page_icon="ER", layout="wide")


@st.cache_resource
def get_engine() -> GameEngine:
    return GameEngine.open(DEFAULT_DB, DEFAULT_WORLD_SEED)


engine = get_engine()
world_id = engine.create_world()

if "character_id" not in st.session_state:
    st.session_state.character_id = None

st.title("Eternal Realms")
st.caption("A persistent world that does not wait for its protagonist.")

if st.session_state.character_id is None:
    living = {row["character_id"]: row for row in engine.living_characters(world_id)}
    if living:
        st.header("Continue a life")
        chosen = st.selectbox(
            "Existing character",
            list(living),
            format_func=lambda cid: (
                f"{living[cid]['name']} · {living[cid]['profession']} · "
                f"Age {living[cid]['age']} · {cid[:8]}"
            ),
        )
        if st.button("Resume character", type="primary"):
            st.session_state.character_id = chosen
            st.session_state.pop("last_message", None)
            st.rerun()
        st.divider()
    st.header("Begin a life")
    with st.form("creation"):
        name = st.text_input("Name", "Wei")
        age = st.number_input("Age", min_value=12, max_value=100, value=18)
        species = st.selectbox("Species", ["Human", "Beast", "Demon", "Spirit", "Machine", "Void Entity"])
        profession = st.selectbox("Profession", ["Farmer", "Merchant", "Soldier", "Blacksmith", "Doctor", "Scholar", "Hunter", "Guard", "Alchemist", "Wanderer"])
        submitted = st.form_submit_button("Enter the world")
    if submitted:
        try:
            st.session_state.character_id = engine.create_character(world_id, name, age, species, "Azure Village", profession, profession)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.pop("last_message", None)
            st.rerun()
    st.info("There is no main quest. Choose a life and see what the years make of it.")
else:
    character = engine.character(st.session_state.character_id)
    if not character["alive"]:
        st.error(f"{character['name']}'s life has ended. Death is permanent.")
        st.write(f"Age at death: {character['age']}")
        st.write(f"Date: {character['death_date'] or 'Unknown'}")
        st.write(f"Cause: {character['death_cause'] or 'Unknown'}")
        if st.button("Return to character selection"):
            st.session_state.character_id = None
            st.session_state.pop("last_message", None)
            st.rerun()
        st.stop()
    date = engine.date(world_id)
    location = engine.db.one("SELECT name, description, terrain FROM locations WHERE location_id = ?", (character["location_id"],))
    with st.sidebar:
        st.subheader("AI Settings")
        ai_mode = st.selectbox("AI Mode", ["OFF", "AUTO", "OLLAMA", "OPENAI"], index=0, key="ai_mode")
        engine.set_ai_provider(provider_for_mode(ai_mode))
        provider_model = getattr(engine.provider, "model", "offline")
        st.caption(f"Provider: {engine.provider.name} · Model: {provider_model}")
        if st.session_state.get("debug_mode", False):
            st.caption("Debug: provider calls are optional; game state remains engine-owned.")
        st.header(character["name"])
        st.write(f"Age {character['age']} · {character['species']}")
        st.write(f"{character['profession']} · {date.text()}")
        st.write(f"{date.season} · {date.weather(engine.seed)}")
        species = engine.species_for_character(character["character_id"])
        bloodline = engine.bloodline_for_character(character["character_id"])
        st.subheader("Life / Biology")
        st.write(f"Species: {species['name']}")
        st.write(f"Origin: {species['origin']}")
        st.write(f"Cultivation affinity: {species['cultivation_affinity']}")
        st.write(f"Bloodline: {bloodline['name'] if bloodline else 'Unmarked'}")
        st.metric("Health", character["health"])
        st.metric("Wealth", character["wealth"])
        st.progress(character["hunger"] / 100, text=f"Nourishment {character['hunger']}%")
        st.progress(character["thirst"] / 100, text=f"Hydration {character['thirst']}%")
        if character["hunger"] <= 15 or character["thirst"] <= 15:
            st.warning("Supplies are running low. Eat food or drink water before advancing time.")
        st.progress(1 - character["fatigue"] / 100, text=f"Energy {100 - character['fatigue']}%")
        family = engine.family(character["character_id"])
        if family:
            st.write(f"Family: {family['name']}")
        relationships = engine.relationships(character["character_id"])
        if relationships:
            st.subheader("Relationships")
            for relationship in relationships:
                st.write(f"{relationship['name']} · trust {relationship['trust']} · familiarity {relationship['familiarity']}")
        if st.button("Save", use_container_width=True):
            engine.save(world_id, character["character_id"])
            st.success("World saved.")
        if st.button("Return to character selection", use_container_width=True):
            st.session_state.character_id = None
            st.session_state.pop("last_message", None)
            st.rerun()
        with st.expander("End this life permanently"):
            st.warning("This character will die permanently. Your world will remain.")
            confirmed = st.checkbox("I understand this cannot be undone", key=f"end-life-{character['character_id']}")
            end_life = st.button("Confirm permanent death", disabled=not confirmed, use_container_width=True)
        if end_life:
            engine.kill_character(character["character_id"], "a dangerous day")
            st.session_state.character_id = None
            st.session_state.pop("last_message", None)
            st.rerun()
    st.subheader(f"{location['name']} · {date.text()}")
    st.write(location["description"])
    st.caption(f"Season: {date.season} · Weather: {date.weather(engine.seed)} · Terrain: {location['terrain']}")
    if st.session_state.get("last_message"):
        st.info(st.session_state.last_message)
    supplies = {row["item"]: row["quantity"] for row in engine.db.all(
        "SELECT item, quantity FROM inventories WHERE character_id = ? AND quantity > 0 ORDER BY item",
        (character["character_id"],),
    )}
    st.subheader("Daily life")
    daily = st.columns(3)
    for column, label, command, disabled in [
        (daily[0], f"Eat food ({supplies.get('Food', 0)})", "eat", not supplies.get("Food") or character["hunger"] >= 100),
        (daily[1], f"Drink water ({supplies.get('Water', 0)})", "drink", not supplies.get("Water") or character["thirst"] >= 100),
        (daily[2], "Rest (8 hours)", "rest", False),
    ]:
        if column.button(label, key=f"daily-{command}", disabled=disabled):
            st.session_state.last_message = engine.perform(character["character_id"], command)
            st.rerun()
    with st.expander("Inventory"):
        if supplies:
            st.table([{"Item": item, "Quantity": qty} for item, qty in supplies.items()])
        else:
            st.caption("Your inventory is empty.")
    with st.form("world-command", clear_on_submit=True):
        command = st.text_input("What do you do?", placeholder="Work for 5 days, cultivate for 30 days, or travel to Eastern Market")
        act = st.form_submit_button("Act", type="primary")
    if act and command.strip():
        st.session_state.last_message = engine.perform(character["character_id"], command)
        st.rerun()
    with st.expander("Economy", expanded=False):
        local_market = engine.market_for_location(world_id, location["name"])
        prices = engine.db.all("SELECT good, unit_price, supply, demand FROM market_prices WHERE market_id = ? ORDER BY good", (local_market["market_id"],))
        st.write(f"**{local_market['name']} market** · Confidence {local_market['confidence']}%")
        if prices:
            st.dataframe([dict(price) for price in prices], hide_index=True, use_container_width=True)
        loans = engine.db.all("SELECT remaining_balance, status, due_day FROM loans WHERE borrower_id = ? ORDER BY rowid DESC", (character["character_id"],))
        if loans:
            st.write("**Loans**")
            st.dataframe([dict(loan) for loan in loans], hide_index=True, use_container_width=True)
        st.caption("Prices respond to local supply, demand, travel, and world events. You can ignore the market and live normally.")
    with st.expander("Travel and communications", expanded=True):
        remaining = engine.exploration_remaining(character["character_id"])
        st.caption(f"Unexplored trails: {remaining} · Exploration takes 6 hours and 12 energy.")
        if st.button("Explore surroundings", key="explore-local", disabled=remaining == 0 or character["fatigue"] > 88):
            st.session_state.last_message = engine.perform(character["character_id"], "explore")
            st.rerun()
        direct_routes = {}
        for route in engine.available_routes(character["character_id"]):
            direct_routes.setdefault(route["destination"], route)
        if direct_routes:
            destination = st.selectbox("Destination", list(direct_routes), key=f"travel-destination-{character['character_id']}-{character['location_id']}")
            route = direct_routes[destination]
            st.write(f"Walking: {route['distance']} day(s) · {route['travel_cost']} coins · {route['terrain']} · Danger {route['danger']}")
            if character["wealth"] < route["travel_cost"]:
                st.caption("You do not have enough coins for this journey.")
            if st.button("Travel to destination", key="travel-go", disabled=character["wealth"] < route["travel_cost"]):
                st.session_state.last_message = engine.perform(character["character_id"], Action("travel", destination))
                st.rerun()
        else:
            st.caption("No direct routes are known from this location.")
        journeys = engine.db.all("SELECT origin, destination, transport_type, status, arrival_serial FROM journeys WHERE traveler_id = ? ORDER BY rowid DESC LIMIT 8", (character["character_id"],))
        if journeys:
            st.write("**Journeys**")
            st.dataframe([dict(journey) for journey in journeys], hide_index=True, use_container_width=True)
        delivered_messages = engine.inbox(character["character_id"])
        st.write(f"**Inbox:** {len(delivered_messages)} delivered message(s)")
        routes = engine.db.all("SELECT from_location, to_location, distance, travel_cost, danger FROM routes WHERE world_id = ? ORDER BY distance LIMIT 8", (world_id,))
        if routes:
            st.write("**Regional routes**")
            st.dataframe([dict(route) for route in routes], hide_index=True, use_container_width=True)
    st.divider()
    cultivation_state = engine.cultivation_state(character["character_id"])
    with st.expander("Cultivation", expanded=True):
        st.write(f"**{realm_name(cultivation_state['realm_id'], cultivation_state['internal_level'])}**")
        st.progress(cultivation_state["cultivation_progress"] / 100, text=f"Progress {cultivation_state['cultivation_progress']}%")
        st.write(f"Foundation {cultivation_state['foundation_integrity']} integrity · Qi control {cultivation_state['qi_control']} · Soul stability {cultivation_state['soul_stability']}")
        st.write(f"Dao comprehension {cultivation_state['dao_comprehension']} · Tribulation pressure {cultivation_state['tribulation_pressure']}")
        cultivation_columns = st.columns(4)
        if cultivation_columns[0].button("Meditate", key="cultivate-meditate"):
            st.session_state.last_message = engine.perform(character["character_id"], "cultivate for 30 days")
            st.rerun()
        if cultivation_columns[1].button("Study Sword Dao", key="cultivate-dao"):
            st.session_state.last_message = engine.study_dao(character["character_id"], "Sword")
            st.rerun()
        if cultivation_columns[2].button("Practice Technique", key="cultivate-technique"):
            st.session_state.last_message = engine.practice_technique(character["character_id"])
            st.rerun()
        if cultivation_columns[3].button("Breakthrough", key="cultivate-breakthrough"):
            st.session_state.last_message = engine.attempt_breakthrough(character["character_id"])
            st.rerun()
        if st.button("Generate tribulation warning", key="tribulation-generate"):
            generated = engine.generate_tribulation(character["character_id"])
            st.session_state.last_message = engine.tribulation_warning(character["character_id"])
            st.rerun()
        if engine.db.one("SELECT tribulation_id FROM tribulations WHERE character_id = ? AND status = 'forming' LIMIT 1", (character["character_id"],)) and st.button("Defend against tribulation", key="tribulation-defend"):
            st.session_state.last_message = engine.resolve_tribulation(character["character_id"], "defend")
            st.rerun()
    with st.expander("Combat", expanded=False):
        combat_targets = engine.nearby_npcs(character["character_id"])
        if combat_targets:
            combat_options = {f"{npc['name']} · {npc['profession']}": npc["npc_id"] for npc in combat_targets}
            combat_label = st.selectbox("Opponent", list(combat_options), key="combat-opponent")
            if character["character_id"] not in engine.active_combats and st.button("Engage", key="combat-engage"):
                engine.start_combat(character["character_id"], combat_options[combat_label])
                st.rerun()
            active_combat = engine.active_combats.get(character["character_id"])
            if active_combat:
                st.write(f"Round {active_combat.round} · {active_combat.terrain} · {active_combat.weather} · {active_combat.distance} meters")
                st.write(active_combat.visible_enemy())
                st.write(f"Your health: {active_combat.player.health} · stamina: {active_combat.player.stamina}")
                combat_action = st.text_input("Combat action", placeholder="Observe, defend, feint, use sword Dao, or flee", key="combat-action")
                if st.button("Commit action", key="combat-commit") and combat_action:
                    st.session_state.last_message = engine.combat_action(character["character_id"], combat_action)
                    st.rerun()
        else:
            st.write("There are no available opponents here.")
    st.subheader("What is happening")
    situations = engine.open_situations(character["character_id"])
    if not situations:
        st.write("Nothing demands your attention right now. That may change.")
    for situation in situations:
        with st.container(border=True):
            st.write(f"**{situation['title']}**")
            st.write(situation["description"])
            for choice in situation["choices"].split("|"):
                if st.button(choice.title(), key=f"situation-{situation['situation_id']}-{choice}"):
                    st.session_state.last_message = engine.resolve_situation(character["character_id"], situation["situation_id"], choice)
                    st.rerun()
    st.subheader("Conversation")
    nearby = engine.nearby_npcs(character["character_id"])
    if nearby:
        npc_options = {f"{npc['name']} · {npc['profession']} · age {npc['age']}": npc["npc_id"] for npc in nearby}
        selected_label = st.selectbox("Talk to", list(npc_options), key="conversation_npc")
        selected_npc = npc_options[selected_label]
        npc_row = engine.db.one("SELECT * FROM npcs WHERE npc_id = ?", (selected_npc,))
        relation = engine.db.one("SELECT * FROM relationships WHERE source_id = ? AND target_id = ?", (character["character_id"], selected_npc))
        emotion = engine.db.one("SELECT mood FROM npc_emotions WHERE npc_id = ?", (selected_npc,))
        st.caption(f"{npc_row['name']} · {npc_row['profession']} · Mood: {emotion['mood'] if emotion else 'Calm'} · Trust: {relation['trust'] if relation else 0}")
        history = list(reversed(engine.conversation_history(character["character_id"], selected_npc, 8)))
        for item in history:
            speaker = "You" if item["speaker_type"] == "PLAYER" else npc_row["name"]
            st.write(f"**{speaker}:** {item['content']}")
        conversation_message = st.text_input("Say something", placeholder="Why did you leave the sect?", key="conversation_message")
        if st.button("Speak", type="primary") and conversation_message:
            st.session_state.last_message = engine.converse(character["character_id"], selected_npc, conversation_message)
            st.rerun()
    else:
        st.write("No one nearby is available for conversation.")
    st.subheader("Recent history")
    events = engine.db.all("SELECT text, year, month, day FROM events WHERE world_id = ? ORDER BY rowid DESC LIMIT 8", (world_id,))
    for event in events:
        st.write(f"Year {event['year']}, Month {event['month']}, Day {event['day']} — {event['text']}")
    journal = engine.journal(character["character_id"])
    tabs = st.tabs(["Journal", "Map", "People", "Family", "Goals"])
    with tabs[0]:
        st.write("**Important memories**")
        for memory in journal["memories"]:
            st.write(f"• {memory['text']}")
        st.write("**Recent events**")
        for event in journal["events"][:10]:
            st.write(f"Day {event['day']}: {event['text']}")
    with tabs[1]:
        st.code(engine.map_text(world_id, character["location_id"]), language="text")
        st.write("Routes are known through travel and local rumor. Dangerous terrain may change a journey.")
    with tabs[2]:
        if journal["relationships"]:
            for person in journal["relationships"]:
                st.write(f"{person['name']} · {person['profession']} · trust {person['trust']} · familiarity {person['familiarity']}")
        else:
            st.write("You have not yet formed a notable relationship.")
    with tabs[3]:
        family = engine.family(character["character_id"])
        st.write(family["name"] if family else "No family record")
        members = engine.db.all("SELECT character_id, role, joined_year FROM family_members WHERE family_id = ?", (family["family_id"],)) if family else []
        for member in members:
            member_row = engine.db.one("SELECT name, alive FROM characters WHERE character_id = ?", (member["character_id"],))
            if member_row:
                st.write(f"{member_row['name']} · {member['role']} · {'alive' if member_row['alive'] else 'dead'}")
    with tabs[4]:
        st.write(f"Short-term: {journal['goals'][0]}")
        st.write(f"Long-term: {journal['goals'][1]}")
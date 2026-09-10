# Eternal Realms

Eternal Realms is a persistent, text-based cultivation-world RPG and simulation. The player is one person in a living world: farming, trading, studying, fighting, cultivating, joining factions, or simply surviving are all valid lives. There is no mandatory main quest and no protagonist protection.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The first run creates `saves/eternal_realms.db`. SQLite is authoritative; Streamlit session state only holds the currently selected character. The database preserves the world, NPCs, events, achievements, actions, and dead characters between browser sessions.

## Architecture

`app.py` is a thin UI adapter. Commands are parsed into structured actions by `game/actions.py`, executed by `GameEngine`, and persisted through `game/database/db.py`. `WorldTick` advances the calendar and scheduled simulation. Narrative text is produced separately by the fallback narrator. AI providers implement an interface and cannot mutate state directly.

The first world is deterministic from its seed and contains a village, market, wilderness, sect, kingdom, factions, locations, and important NPCs. Characters have persistent identities, professions, cultivation stats, inventories, relationships-ready records, event history, achievements, death records, and legacy history.

Phase 2 adds a lived-in loop: seasons and deterministic weather, hunger/thirst/fatigue, NPC daily routines, route-aware travel with costs and danger, buying and selling, contextual situations with choices, memories, family records, relationship history, an ASCII map, and journal views for events, people, family, goals, and memories. Existing SQLite saves are migrated additively when opened.

## Phase 3 AI and Conversations

Important NPCs have bounded context built from their profession, faction, personality, relationship, memories, explicit knowledge, secrets, mood, location, and recent conversation. Conversations and messages are persisted. The fallback brain works offline and refuses to invent facts outside the NPC's known information. Dialogue may propose social changes, but `GameEngine` validates and applies those changes.

AI is optional. The sidebar supports `OFF`, `AUTO`, `OLLAMA`, and `OPENAI`. Offline mode requires no credentials:

```bash
AI_PROVIDER=none streamlit run app.py
```

For Ollama, set `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434/v1/`, and `OLLAMA_MODEL` to a model installed locally. For OpenAI, set `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL`. `AUTO` checks Ollama first, then uses OpenAI when configured, otherwise the fallback brain. Provider failures return to fallback dialogue and do not change authoritative state.

## Phase 4 Cultivation and Combat

The cultivation state is now data-driven and additive to existing characters. It tracks 50 expandable major realms, five internal stages, foundation quality and integrity, body, qi control and quality, soul stability, comprehension, Dao progression, preparation, deviation risk, and tribulation pressure. Dao paths and technique mastery are persisted separately. Cultivation methods change progress and risk based on location and preparation; breakthroughs can fail, damage the foundation, or advance an internal stage. Tribulations have types, tiers, severity, spotting, warnings, preparation, and deterministic outcomes.

Combat now has meaningful exchange beats with distance, terrain, weather, visibility, stamina, soul, morale, positions, statuses, injuries, observation, feints, techniques, Dao actions, negotiation, and escape. Enemy condition is narrated through perception rather than exposed as raw HP. Finished fights are written to combat history and death remains permanent.

## Phase 11 Economy

The economy is authoritative and persistent in SQLite. Local markets create deterministic prices from supply and demand, and player purchases and sales write traceable `trade_transactions` records while preserving the original inventory and command APIs. Market state advances with the existing world clock.

The banking foundation supports persistent banks, bounded loans, interest, repayment, defaults, and economic events. Currency and trade-route records are extensible for later regional exchange, taxation, corporations, and war-driven supply disruption. The Streamlit Economy panel shows local prices and personal loans; players can ignore it and continue ordinary work, cultivation, travel, or combat.

Economic simulation is intentionally aggregated: markets and active loans update on calendar advancement rather than simulating every household transaction. This keeps long runs stable and leaves room for richer business, labor, and corporate actors in later phases.

## Phase 12 Transportation

Transportation is persisted through `TransportEngine`. Player travel creates a journey with a route, transport method, departure, ETA, status, and current location; the world clock advances it rather than treating movement as an instant state change. Cargo journeys, warehouses, infrastructure condition, and delayed messages use the same calendar-driven simulation.

The first transport layer supports walking, animals, horses, carts, caravans, boats, ships, rail, aircraft, spirit boats, and teleportation as data-driven speed/capacity choices. Existing route records remain authoritative, while new routes can be constructed through the engine. Messages have delivery latency and remain in transit until the world reaches their delivery time. The Streamlit Transport and Communications panel exposes journeys, messages, and known routes without requiring the player to manage them.

Simulation is aggregated: only active journeys, cargo, messages, and infrastructure for the current world are updated on day boundaries. The schema is additive, so existing saves retain their original routes and characters.

## Tests

```bash
pytest -q
```

## Roadmap

Next steps are richer relationship simulation, market supply and demand, faction politics, procedural regional expansion, full family and legacy discovery, and optional Ollama/OpenAI adapters. These additions should continue to treat SQLite and deterministic engine rules as the source of truth.# REALMS
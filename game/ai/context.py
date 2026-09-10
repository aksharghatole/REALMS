from dataclasses import dataclass

from game.database.db import Database


@dataclass(frozen=True)
class NPCContext:
    npc_id: str
    player_id: str
    text: str


class NPCContextBuilder:
    """Selects a small, ranked view of NPC state for conversation."""

    def __init__(self, db: Database, memory_limit: int = 8, knowledge_limit: int = 8):
        self.db = db
        self.memory_limit = memory_limit
        self.knowledge_limit = knowledge_limit

    def build(self, player_id: str, npc_id: str) -> NPCContext:
        npc = self.db.one("SELECT * FROM npcs WHERE npc_id = ?", (npc_id,))
        player = self.db.one("SELECT name, profession, reputation, wealth FROM characters WHERE character_id = ?", (player_id,))
        if npc is None or player is None:
            raise ValueError("Conversation participant does not exist")
        faction = self.db.one("SELECT name, type FROM factions WHERE faction_id = ?", (npc["faction_id"],)) if npc["faction_id"] else None
        relationship = self.db.one("SELECT trust, respect, fear, love, hatred, familiarity FROM relationships WHERE source_id = ? AND target_id = ?", (player_id, npc_id))
        emotions = self.db.one("SELECT * FROM npc_emotions WHERE npc_id = ?", (npc_id,))
        memories = self.db.all("SELECT text, importance, truth FROM memories WHERE owner_id IN (?, ?) ORDER BY importance DESC, rowid DESC LIMIT ?", (npc_id, player_id, self.memory_limit))
        knowledge = self.db.all("SELECT subject, content, confidence, truth_status FROM npc_knowledge WHERE npc_id = ? ORDER BY confidence DESC, acquired_day DESC LIMIT ?", (npc_id, self.knowledge_limit))
        conversations = self.db.all("SELECT m.speaker_type, m.content FROM conversation_messages m JOIN conversations c ON c.conversation_id = m.conversation_id WHERE c.player_id = ? AND c.npc_id = ? ORDER BY m.created_day DESC, m.rowid DESC LIMIT 6", (player_id, npc_id))
        lines = [f"NPC: {npc['name']}, age {npc['age']}, profession {npc['profession']}, status {npc['social_status']}", f"Personality: {npc['personality']}", f"Goals: {npc['goals']}", f"Fears: {npc['fears']}", f"Ambition: {npc['ambition']}", f"Player: {player['name']}, profession {player['profession']}, reputation {player['reputation']}"]
        if faction:
            lines.append(f"Faction: {faction['name']} ({faction['type']})")
        if relationship:
            lines.append(f"Relationship: trust {relationship['trust']}, respect {relationship['respect']}, fear {relationship['fear']}, love {relationship['love']}, hatred {relationship['hatred']}, familiarity {relationship['familiarity']}")
        if emotions:
            lines.append(f"Mood: {emotions['mood']}; happiness {emotions['happiness']}, anger {emotions['anger']}, fear {emotions['fear']}, stress {emotions['stress']}")
        lines.append("Relevant memories: " + ("; ".join(memory["text"] for memory in memories) or "none"))
        lines.append("Known facts and beliefs: " + ("; ".join(f"{item['subject']}: {item['content']} ({item['truth_status']})" for item in knowledge) or "none"))
        lines.append("Recent conversation: " + ("; ".join(f"{item['speaker_type']}: {item['content']}" for item in reversed(conversations)) or "none"))
        return NPCContext(npc_id, player_id, "\n".join(lines))
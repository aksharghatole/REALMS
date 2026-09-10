import re
import uuid

from game.ai.brain import NPCBrain
from game.ai.context import NPCContextBuilder
from game.ai.provider import AIProvider
from game.clock import GameDate
from game.database.db import Database


class ConversationService:
    """Persists dialogue and applies only validated, deterministic consequences."""

    def __init__(self, db: Database, seed: int, provider: AIProvider):
        self.db = db
        self.seed = seed
        self.provider = provider
        self.contexts = NPCContextBuilder(db)
        self.brain = NPCBrain(provider)

    def converse(self, player_id: str, npc_id: str, message: str) -> str:
        player = self.db.one("SELECT * FROM characters WHERE character_id = ?", (player_id,))
        npc = self.db.one("SELECT * FROM npcs WHERE npc_id = ?", (npc_id,))
        if player is None or npc is None or player["world_id"] != npc["world_id"]:
            return "That conversation cannot happen."
        if player["location_id"] != npc["location_id"]:
            return "They are not here."
        world = self.db.one("SELECT year, month, day FROM worlds WHERE world_id = ?", (player["world_id"],))
        date = GameDate(world["year"], world["month"], world["day"])
        conversation = self.db.one("SELECT * FROM conversations WHERE player_id = ? AND npc_id = ? ORDER BY last_day DESC LIMIT 1", (player_id, npc_id))
        if conversation is None:
            conversation_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?, '', 1)", (conversation_id, player["world_id"], player_id, npc_id, player["location_id"], date.day_of_year, date.day_of_year))
        else:
            conversation_id = conversation["conversation_id"]
        self.db.execute("INSERT INTO conversation_messages VALUES (?, ?, 'PLAYER', ?, ?, ?, 'TALK')", (str(uuid.uuid4()), conversation_id, player_id, message, date.day_of_year))
        intent = self._safe_intent(message)
        self._apply_consequence(player_id, npc_id, intent, message)
        response = self.brain.respond(self.contexts.build(player_id, npc_id), message)
        self.db.execute("INSERT INTO conversation_messages VALUES (?, ?, 'NPC', ?, ?, ?, 'TALK')", (str(uuid.uuid4()), conversation_id, npc_id, response, date.day_of_year))
        self.db.execute("UPDATE conversations SET last_day = ?, summary = ? WHERE conversation_id = ?", (date.day_of_year, self._summary(message, response), conversation_id))
        self._remember(player, npc, message, response, date.day_of_year)
        return response

    def _safe_intent(self, message: str) -> str:
        allowed = {"TALK", "ASK", "PERSUADE", "THREATEN", "INSULT", "COMPLIMENT", "NEGOTIATE", "OFFER", "REQUEST", "PROMISE", "LIE", "REVEAL_INFORMATION", "HELP", "BETRAY"}
        try:
            value = self.provider.interpret_player_input(message)
            intent = str(value.get("intent", "TALK")).upper()
            if intent in allowed and intent != "TALK":
                return intent
        except (AttributeError, TypeError, ValueError):
            pass
        lower = message.lower()
        if any(word in lower for word in ("threaten", "kill you", "hurt you")):
            return "THREATEN"
        if "promise" in lower or "will protect" in lower:
            return "PROMISE"
        if "betray" in lower:
            return "BETRAY"
        if "help" in lower:
            return "HELP"
        return "TALK"

    def _apply_consequence(self, player_id: str, npc_id: str, intent: str, message: str) -> None:
        player = self.db.one("SELECT world_id FROM characters WHERE character_id = ?", (player_id,))
        relation = self.db.one("SELECT * FROM relationships WHERE source_id = ? AND target_id = ?", (player_id, npc_id))
        relation_id = relation["relationship_id"] if relation else str(uuid.uuid4())
        deltas = {"THREATEN": ( -8, 0, 12), "INSULT": (-6, 0, 3), "BETRAY": (-15, -4, 0), "PROMISE": (4, 2, 0), "HELP": (6, 2, 0), "COMPLIMENT": (3, 2, 0)}
        trust, respect, fear = deltas.get(intent, (0, 0, 0))
        if relation:
            self.db.execute("UPDATE relationships SET trust = MAX(0, MIN(100, trust + ?)), respect = MAX(0, MIN(100, respect + ?)), fear = MAX(0, MIN(100, fear + ?)), familiarity = MIN(100, familiarity + 1) WHERE relationship_id = ?", (trust, respect, fear, relation_id))
        else:
            self.db.execute("INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 1)", (relation_id, player["world_id"], player_id, npc_id, max(0, trust), max(0, respect), fear))
        self.db.execute("INSERT OR IGNORE INTO npc_emotions (npc_id) VALUES (?)", (npc_id,))
        if intent == "THREATEN":
            self.db.execute("UPDATE npc_emotions SET fear = MIN(100, fear + 10), anger = MIN(100, anger + 5), mood = 'Afraid' WHERE npc_id = ?", (npc_id,))
        elif intent in {"HELP", "PROMISE", "COMPLIMENT"}:
            self.db.execute("UPDATE npc_emotions SET happiness = MIN(100, happiness + 4), stress = MAX(0, stress - 3), mood = 'Hopeful' WHERE npc_id = ?", (npc_id,))

    def _remember(self, player, npc, message: str, response: str, day: int) -> None:
        importance = 3 if any(word in message.lower() for word in ("promise", "secret", "betray", "kill", "truth")) else 1
        self.db.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, 'true')", (str(uuid.uuid4()), player["world_id"], npc["npc_id"], f"{player['name']} said: {message[:300]}", importance))
        self.db.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, 'true')", (str(uuid.uuid4()), player["world_id"], player["character_id"], f"Spoke with {npc['name']}: {message[:300]}", importance))
        if any(word in message.lower() for word in ("i know", "the truth", "i saw")):
            self.db.execute("INSERT INTO npc_knowledge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), player["world_id"], npc["npc_id"], "player_claim", message[:300], "player", 35, day, "belief"))

    def _summary(self, message: str, response: str) -> str:
        return re.sub(r"\s+", " ", f"Player: {message} NPC: {response}")[:800]

    def history(self, player_id: str, npc_id: str, limit: int = 12) -> list:
        return self.db.all("SELECT speaker_type, content, created_day FROM conversation_messages m JOIN conversations c ON c.conversation_id = m.conversation_id WHERE c.player_id = ? AND c.npc_id = ? ORDER BY m.rowid DESC LIMIT ?", (player_id, npc_id, limit))
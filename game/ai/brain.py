from game.ai.context import NPCContext
from game.ai.provider import AIProvider


class NPCBrain:
    """Language layer for an NPC; it can speak, but cannot mutate game state."""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def respond(self, context: NPCContext, player_message: str) -> str:
        generated = self.provider.generate_npc_response(context.text, player_message).strip()
        return generated or self._fallback(context.text, player_message)

    def _fallback(self, context: str, message: str) -> str:
        lower = message.lower()
        npc_name = context.split("NPC: ", 1)[1].split(",", 1)[0]
        known_facts = next((line for line in context.splitlines() if line.startswith("Known facts and beliefs:")), "")
        relationship_line = next((line for line in context.splitlines() if line.startswith("Relationship:")), "")
        trust = int(relationship_line.split("trust ", 1)[1].split(",", 1)[0]) if "trust " in relationship_line else 0
        fear = int(relationship_line.split("fear ", 1)[1].split(",", 1)[0]) if "fear " in relationship_line else 0
        if any(word in lower for word in ("threaten", "kill", "hurt")):
            return "Please lower your voice. I do not want trouble." if fear < 50 else "I will tell you nothing. Leave me alone."
        if "northern" in lower or "ruin" in lower or "governor" in lower:
            if "northern" not in known_facts.lower() and "ruin" not in known_facts.lower() and "governor" not in known_facts.lower():
                return "I do not know anything reliable about that. Ask someone who travels farther than I do."
        if "trust" in lower:
            return "I believe you" if trust >= 60 else "We have not known each other long enough for that."
        if "secret" in lower or "truth" in lower:
            return "There are things I would rather not discuss in the open." if trust < 70 else "Ask me plainly, and I may answer."
        if "promise" in lower or "help" in lower:
            return "That is a serious promise. I will remember that you offered." if trust >= 20 else "Kind words are easy. Why should I believe you?"
        profession = next((line.split("profession ", 1)[1].split(",", 1)[0] for line in context.splitlines() if line.startswith("NPC:")), "villager")
        opening = "You have helped me before; I will hear you out." if trust >= 60 else "What do you need?"
        return f"{opening} I am only a {profession}, but {npc_name} knows the rhythms of this place."
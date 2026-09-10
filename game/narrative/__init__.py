"""Fallback narrative package."""

from game.clock import GameDate


def action_message(action: str, date: GameDate) -> str:
	messages = {"farm": "You work the village fields. Your hands ache, but the harvest improves.", "rest": "You rest and let your body recover.", "cultivate": "You guide qi through your meridians. Your foundation feels a little steadier.", "travel": "You travel along the old road and arrive at your destination.", "talk": "You exchange cautious words and learn a little about village life.", "look": "The village is alive with ordinary work, quiet ambitions, and distant possibilities."}
	return messages.get(action, f"Time passes under the changing sky. ({date.text()})")
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Action:
    verb: str
    target: str = ""
    duration: int = 1


def parse_command(text: str) -> Action:
    command = text.strip().lower()
    duration_match = re.search(r"(\d+)\s*(?:days?|months?|years?)", command)
    duration = int(duration_match.group(1)) if duration_match else 1
    if "month" in command:
        duration *= 30
    elif "year" in command:
        duration *= 360
    for verb, aliases in {
        "look": ("look", "what do i see", "map"),
        "status": ("status", "character"),
        "inventory": ("inventory", "items"),
        "farm": ("farm", "work", "harvest"),
        "cultivate": ("cultivate", "meditate", "breakthrough"),
        "rest": ("rest", "sleep", "eat"),
        "travel": ("travel", "go to", "visit"),
        "talk": ("talk", "speak", "chat"),
        "save": ("save",),
        "buy": ("buy", "purchase"),
        "sell": ("sell",),
        "help_situation": ("help ",),
        "ignore": ("ignore",),
        "investigate": ("investigate", "question"),
    }.items():
        if any(alias in command for alias in aliases):
            if " to " in command:
                target = command.split(" to ", 1)[1]
            else:
                target = ""
                for alias in aliases:
                    if command.startswith(alias + " "):
                        target = command[len(alias) + 1:].split(" for ", 1)[0].strip()
                        break
            return Action(verb, target, duration)
    return Action("help")
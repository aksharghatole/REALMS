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
        "market": ("market", "prices", "price"),
        "balance": ("balance", "wealth", "economy"),
        "routes": ("routes", "transport", "journey"),
        "inbox": ("inbox", "messages", "mail"),
        "talk": ("talk", "speak", "chat"),
        "save": ("save",),
        "buy": ("buy", "purchase"),
        "sell": ("sell",),
        "join": ("join", "join the", "join a"),
        "leave": ("leave", "leave the", "quit"),
        "enlist": ("enlist", "join the army", "join army"),
        "help_situation": ("help ",),
        "ignore": ("ignore",),
        "investigate": ("investigate", "question"),
    }.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", command) for alias in aliases):
            if " to " in command:
                target = command.split(" to ", 1)[1]
            else:
                target = ""
                for alias in aliases:
                    if command.startswith(alias + " "):
                        target = command[len(alias) + 1:].split(" for ", 1)[0].strip()
                        break
                    if command.startswith(alias) and alias in {"join", "leave"}:
                        target = command[len(alias):].strip()
                        break
            if verb in {"join", "leave", "enlist"} and target:
                target = re.sub(r"^(the|a|an)\s+", "", target, flags=re.I)
            return Action(verb, target, duration)
    return Action("help")
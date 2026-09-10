import uuid

DAO_PATHS = ("Sword", "Fire", "Water", "Earth", "Wind", "Lightning", "Space", "Time", "Life", "Death", "Blood", "Soul", "Dream", "Illusion", "Alchemy", "Formation", "Karma", "Destruction", "Creation", "Cause and Effect", "Chaos", "Star", "Void")


def seed_dao_paths(db) -> None:
    for name in DAO_PATHS:
        db.execute("INSERT OR IGNORE INTO dao_paths VALUES (?, ?, ?, ?)", (str(uuid.uuid5(uuid.NAMESPACE_DNS, f"dao:{name}")), name, "classical", f"The principles and practice of {name} Dao."))


def dao_name(db, dao_id: str) -> str:
    row = db.one("SELECT name FROM dao_paths WHERE dao_id = ?", (dao_id,))
    return row["name"] if row else "Unknown Dao"
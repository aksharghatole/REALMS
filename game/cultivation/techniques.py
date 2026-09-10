import uuid

TECHNIQUE_SEEDS = (("Breath of Still Water", "Qi", 0, "Mortal", "qi +8; control +2", "overexertion"), ("Azure Village Staff", "Staff", 0, "Mortal", "combat +5", "fatigue"), ("Cloudstep Footwork", "Movement", 3, "Spirit", "escape +8; movement +5", "qi drain"))


def seed_techniques(db) -> None:
    for name, category, realm, quality, effects, risks in TECHNIQUE_SEEDS:
        db.execute("INSERT OR IGNORE INTO techniques (technique_id, name, category, required_realm, quality, effects, risks) VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid5(uuid.NAMESPACE_DNS, f"technique:{name}")), name, category, realm, quality, effects, risks))


def mastery_name(value: int) -> str:
    return ("Novice", "Familiar", "Trained", "Proficient", "Expert", "Master", "Grandmaster", "Perfect", "Transcendent")[max(0, min(value // 10, 8))]
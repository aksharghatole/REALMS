BLOODLINES = {
    "Ancient Dragon": {"family": "beast", "purity": 1.0, "strength": 1.15, "inheritance": 1.0, "mutation": 0.1, "awakening": 0.2, "evolution": 0.1},
    "Phoenix": {"family": "avian", "purity": 0.95, "strength": 1.12, "inheritance": 1.05, "mutation": 0.15, "awakening": 0.3, "evolution": 0.15},
    "Qilin": {"family": "beast", "purity": 0.9, "strength": 1.1, "inheritance": 1.0, "mutation": 0.1, "awakening": 0.2, "evolution": 0.12},
    "Void Beast": {"family": "void", "purity": 0.85, "strength": 1.18, "inheritance": 0.9, "mutation": 0.3, "awakening": 0.35, "evolution": 0.2},
    "Star Beast": {"family": "celestial", "purity": 0.8, "strength": 1.14, "inheritance": 0.85, "mutation": 0.2, "awakening": 0.25, "evolution": 0.15},
    "Demon": {"family": "demon", "purity": 0.75, "strength": 1.12, "inheritance": 0.8, "mutation": 0.25, "awakening": 0.25, "evolution": 0.18},
    "Primordial Beast": {"family": "primordial", "purity": 1.2, "strength": 1.25, "inheritance": 1.1, "mutation": 0.4, "awakening": 0.45, "evolution": 0.3},
}

PHYSIQUES = (
    "Mortal Body",
    "Iron Body",
    "Jade Body",
    "Heavenly Sword Body",
    "Nine Yin Body",
    "Nine Yang Body",
    "Void Body",
    "Chaos Body",
    "Primordial Body",
    "Immortal Bone Body",
    "Star Devouring Body",
    "Samsara Body",
    "Demon God Body",
)

PHYSIQUE_MODIFIERS = {
    "Mortal Body": {"body": 0.9, "qi": 0.95, "survival": 1.0},
    "Iron Body": {"body": 1.1, "qi": 0.98, "survival": 1.08},
    "Jade Body": {"body": 1.2, "qi": 1.0, "survival": 1.1},
    "Heavenly Sword Body": {"body": 1.25, "qi": 1.05, "survival": 1.15},
    "Nine Yin Body": {"body": 1.2, "qi": 1.1, "survival": 1.08},
    "Nine Yang Body": {"body": 1.35, "qi": 1.0, "survival": 1.12},
    "Void Body": {"body": 1.35, "qi": 1.2, "survival": 1.18},
    "Chaos Body": {"body": 1.6, "qi": 1.4, "survival": 1.3},
    "Primordial Body": {"body": 1.85, "qi": 1.5, "survival": 1.45},
    "Immortal Bone Body": {"body": 1.4, "qi": 1.12, "survival": 1.2},
    "Star Devouring Body": {"body": 1.45, "qi": 1.18, "survival": 1.26},
    "Samsara Body": {"body": 1.5, "qi": 1.25, "survival": 1.3},
    "Demon God Body": {"body": 1.7, "qi": 1.3, "survival": 1.35},
}


def physique_modifier(name: str) -> dict:
    return PHYSIQUE_MODIFIERS.get(name, {"body": 1.0, "qi": 1.0, "survival": 1.0})


def bloodline_family(name: str) -> str:
    return BLOODLINES.get(name, {}).get("family", "mortal")


def bloodline_modifier(name: str) -> dict:
    return BLOODLINES.get(name, {"family": "mortal", "purity": 1.0, "strength": 1.0, "inheritance": 1.0, "mutation": 0.0, "awakening": 0.0, "evolution": 0.0})

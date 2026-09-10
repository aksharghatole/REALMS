from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAVE_DIR = ROOT / "saves"
DEFAULT_DB = SAVE_DIR / "eternal_realms.db"
DEFAULT_WORLD_SEED = 184729

SAVE_DIR.mkdir(exist_ok=True)
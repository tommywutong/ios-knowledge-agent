from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_config():
    import yaml
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(p):
    path = Path(p).expanduser()
    return path if path.is_absolute() else ROOT / path

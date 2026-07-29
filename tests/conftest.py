from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(REPO_ROOT / ".env")


import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def get_database_path():
    configured_path = os.environ.get(
        "CREDISENSE_DB_PATH"
    )

    if configured_path:
        path = Path(configured_path).expanduser()

        if not path.is_absolute():
            path = BASE_DIR / path

        return path.resolve()

    return BASE_DIR / "credisense.db"


DB_PATH = get_database_path()

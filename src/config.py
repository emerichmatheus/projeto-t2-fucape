"""Configuração central do projeto, lida de variáveis de ambiente."""
import os
from pathlib import Path

DEFAULT_APP_IDS = "730,570,271590,1172470,578080,252490,1245620,413150"

STEAM_APP_IDS = [
    int(x) for x in os.getenv("STEAM_APP_IDS", DEFAULT_APP_IDS).split(",")
    if x.strip()
]
STEAM_MAX_PAGES = int(os.getenv("STEAM_MAX_PAGES", "20"))
STEAM_LANGUAGE = os.getenv("STEAM_LANGUAGE", "brazilian")
STEAM_POLITE_PAUSE = float(os.getenv("STEAM_POLITE_PAUSE", "1.0"))
STEAM_SIMULATE_429_RATE = float(os.getenv("STEAM_SIMULATE_429_RATE", "0"))

RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data"))
RAW_REVIEWS_DIR = RAW_DATA_DIR / "raw" / "steam_reviews"
RAW_APPDETAILS_DIR = RAW_DATA_DIR / "raw" / "steam_appdetails"
STAGING_DIR = RAW_DATA_DIR / "staging"

DDL_PATH = Path(os.getenv(
    "DDL_PATH", Path(__file__).resolve().parent / "warehouse" / "ddl.sql"
))

DW_CONN_ID = "dw_postgres"


def dw_sqlalchemy_url() -> str:
    """URL do DW para uso fora do Airflow (painel e benchmark)."""
    user = os.getenv("DW_USER", "dw")
    pwd = os.getenv("DW_PASSWORD", "dw")
    host = os.getenv("DW_HOST", "localhost")
    port = os.getenv("DW_PORT", "5433")
    db = os.getenv("DW_DB", "steam_dw")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"

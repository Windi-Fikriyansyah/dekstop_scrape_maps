from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

import sys
from pathlib import Path

# Identify if running as a bundled EXE or script
if getattr(sys, 'frozen', False):
    # If bundled, store data in User's AppData to avoid permission issues in Program Files
    app_data = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "WAMaps"
    app_data.mkdir(parents=True, exist_ok=True)
    db_path = app_data / "sql_app_v2.db"
else:
    # If running as script, keep it local
    db_path = Path("./sql_app_v2.db").resolve()

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

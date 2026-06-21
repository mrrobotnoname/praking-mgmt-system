
from pathlib import Path
from sqlmodel import Session,create_engine,SQLModel
from app import models

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR/ "parking.db"
DB_URI:str =f"sqlite:///{DB_PATH}"



engine = create_engine(DB_URI,connect_args={"check_same_thread": False})

def init_db():
    "Create the table if the tables alredy not in the database"
    SQLModel.metadata.create_all(engine)

def get_session():
    """FastAPI Dependency to provide an isolated database transaction per request."""
    with Session(engine) as session:
        yield session

from sqlmodel import Session,create_engine,SQLModel

db_name:str = "parking-mgmt-system.db"
db_url:str =f"sqlite:///{db_name}"


engine = create_engine(db_url,connect_args={"check_same_thread": False})

def init_db():
    "Create the table if the tables alredy not in the database"
    SQLModel.metadata.create_all(engine)

def get_session():
    """FastAPI Dependency to provide an isolated database transaction per request."""
    with Session(engine) as session:
        yield session
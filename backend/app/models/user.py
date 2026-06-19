from typing import Annotated

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    
    user_id: int | None = Field(default=None, primary_key=True, index=True)
    username: str = Field(unique=True, index=True)
    password: str
    name: str
    phone_number: str = Field(unique=True)
    role:str= Field(default="guard")


from typing import Optional,List
from datetime import datetime, timezone
from sqlmodel import SQLModel,Field,Relationship
from app.models.parking_log import ParkingLog


class Owner(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True)
    
    phone_number: str = Field(unique=True, index=True) 
    email: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    logs: List["ParkingLog"] = Relationship(back_populates="owner")
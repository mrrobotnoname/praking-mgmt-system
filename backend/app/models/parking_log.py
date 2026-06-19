from typing import Optional,List
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from app.models.owner import Owner

class ParkingLog(SQLModel, table=True):
    """
    Tracks every single check-in and check-out transaction.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    vehicle_plate: str = Field(index=True)
    
    check_in_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    check_out_time: Optional[datetime] = Field(default=None)
    fee_charged: Optional[float] = Field(default=None)

    slot_id: int = Field(foreign_key="parkingslot.id")
    vehicle_id: int = Field(foreign_key="vehicletype.id")
    
    owner_id: Optional[int] = Field(default=None, foreign_key="owner.id")


    owner: Optional[Owner] = Relationship(back_populates="logs")
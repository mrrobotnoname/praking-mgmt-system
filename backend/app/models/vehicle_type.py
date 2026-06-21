from typing import List, Optional,TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from backend.app.models.pricing import Pricing
    from backend.app.models.slot import ParkingSlot

class VehicleType(SQLModel, table=True):
    vehicle_id: int | None = Field(default=None, primary_key=True)
    vehicle_type: str = Field(nullable=False, unique=True)
    
    slots: List["ParkingSlot"] = Relationship(back_populates="vehicle_type")
    pricing: Optional["Pricing"] = Relationship(back_populates="vehicle_type")


from typing import Optional,TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from backend.app.models.vehicle_type import VehicleType
    

class ParkingSlot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    floor: str | None = Field(default=None, index=True)
    slot_number: int = Field(index=True)
    
    is_accessible: bool = Field(default=False)#for desable area 
    is_occupied: bool = Field(default=False)

    vehicle_type_id: int = Field(foreign_key="vehicletype.vehicle_id")
    vehicle_type: Optional["VehicleType"] = Relationship(back_populates="slots")

    @property
    def display_slot(self)->str:
        if self.floor:
            return f"{self.floor}-{self.slot_number}".upper()
        return str(self.slot_number)


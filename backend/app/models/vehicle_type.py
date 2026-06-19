from typing import List

from sqlmodel import Field, SQLModel, Relationship

from backend.app.models.slot import ParkingSlot


class VehicleType(SQLModel, tabel=True):
    vehicle_id: int | None = Field(default=None, primary_key=True)
    vehicle_type: str = Field(nullable=False, unique=True)
    slots: List["ParkingSlot"] = Relationship(back_populates="vehicle")

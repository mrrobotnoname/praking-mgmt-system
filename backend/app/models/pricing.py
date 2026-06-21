
from typing import Optional,TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from backend.app.models.vehicle_type import VehicleType

class Pricing(SQLModel, table=True):
    """
    Stores pricing configurations for each vehicle type.
    Handles hourly rates and a fixed/cap switch after a certain duration.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Rates
    hourly_rate: float = Field(default=0.0)
    fixed_rate: float = Field(default=0.0)      # The flat/cap price applied if threshold is passed
    
    # Threshold in minutes (e.g., 180 minutes = 3 hours)
    threshold_minutes: int = Field(default=180) 

    # Foreign Key linking to VehicleType (1-to-1 relationship)
    vehicle_type_id: int = Field(foreign_key="vehicletype.vehicle_id", unique=True)
    vehicle_type: Optional["VehicleType"] = Relationship(back_populates="pricing")

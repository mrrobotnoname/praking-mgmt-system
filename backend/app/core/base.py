from pydantic import BaseModel

#Object model for guards
class Guard(BaseModel):
    username: str
    password: str
    name: str
    phone_number: str


class GuardRespond(BaseModel):
    user_id: int
    username: str
    name: str
    phone_number: str


class GuardUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    name: str | None = None
    phone_number: str | None = None



#Object Model for Vehicle_type


class Vehicle(BaseModel):
    vehicle_type:str | None = None
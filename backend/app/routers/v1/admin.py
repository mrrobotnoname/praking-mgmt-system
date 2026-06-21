from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from typing import List


from app.routers.deps import isAdmin
from app.db.session import get_session
from app.core.security import validate_password, encryptPassword

from app.models.user import User
from app.models.vehicle_type import VehicleType
from app.core.base import Guard,GuardRespond,GuardUpdate, Vehicle


router = APIRouter(
    prefix="/api/v1/admin",
    dependencies=[Depends(isAdmin)] 
)



@router.get("/")
def admin():
    return "welcom to the admin"


# =============================================Guard haddling fucntions ===========================================
# ===== Create the guard acoount ====
@router.post("/guard/add")
def create_guard_account(data: Guard, db: Session = Depends(get_session)):
    user = db.exec(select(User)
                   .where(User.username == data.username)
                   .where(User.role == "guard")).first()

    # username validation
    if user and user is not None:
        raise HTTPException(status_code=409, detail="username already taken")

    # password validation
    if not validate_password(data.password):
        raise HTTPException(
            status_code=400, detail="Password is not strong please enter another password")

    new_user = User(
        username=data.username,
        password=encryptPassword(data.password),
        name=data.name,
        phone_number=data.phone_number,
        role="guard"
    )
    try:
        db.add(new_user)
        db.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="phone number should be unique")

    return f"Guard:{data.name} added to the system."

# ====== get all the guard acoounts ====


@router.get("/guards/all", response_model=List[GuardRespond])
def get_guards(db: Session = Depends(get_session)):
    guards: tuple = db.exec(select(User).where(User.role == "guard")).all()
    return guards

# === delete the guard accounts


@router.delete("/guard/delete/{guard_id}")
def deleteGuard(guard_id: int, db: Session = Depends(get_session)):
    result = db.exec(select(User).where(User.role == "guard").where(
        User.user_id == guard_id)).first()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Guard not found"
        )

    db.delete(result)
    db.commit()
    return {
        "message": f"Guard: {result.username} was deleted successfuly!"
    }


# ==== modify guard accounts =======
@router.patch("/guard/edit/{guard}")
def editGuard(
    data: GuardUpdate,
    guard_id: int,
    db: Session = Depends(get_session)
):
    guard = db.exec(select(User).where(
        User.user_id == guard_id).where(User.role == "guard")).first()

    if not guard:
        raise HTTPException(
            status_code=404,
            detail="No guard found!"
        )
    if data.username is not None:
        exsist = db.exec(select(User).where(
            User.username == data.username)).first()

        if exsist:
            raise HTTPException(
                status_code=409,
                detail="username already taken."
            )
        guard.username = data.username
    if data.name is not None:
        guard.name = data.name

    if data.password is not None:
        if not validate_password(data.password):
            return {
                "message": "The password is too week try another one!"
            }
        guard.password = encryptPassword(data.password)
    if data.phone_number is not None:
        exsist = db.exec(select(User).where(
            User.phone_number == data.phone_number).where(User.role == "guard")).first()
        
        if exsist is not None:
            raise HTTPException(
                code=409,
                detail="phone number already exist"
            )
        guard.phone_number = data.phone_number
    try:
        db.add(guard)
        db.commit()
        db.refresh(guard)
        return "update successfuly"
    except:
        return "Somthing went wrong please try again"


# ==================================================================================

# ===================== Vehicle & Pricing Configuration ===================

@router.get("/all-vehicle",response_model=List[Vehicle])
def getVehicle(db:Session=Depends(get_session)):

    vehicle= db.exec(select(VehicleType)).all()

    return vehicle
    

@router.post("/add-vehicle")
def addVehicle(data:Vehicle,db:Session=Depends(get_session)):
    exist = db.exec(select(VehicleType)
                    .where(VehicleType.vehicle_type == data.vehicle_type)).first()
    
    if exist:
        raise HTTPException(
            status_code=404,
            detail="vehicle type alredy exist."
        )
    vehicle = VehicleType(vehicle_type=data.vehicle_type)
    db.add(vehicle)
    db.commit()

    return{
        "message": f"{data.vehicle_type} added to the system."
    }
@router.delete("/delete-vehicle/{vehicle_id}")
def deleteVehicle(vehicle_id:int,db:Session=Depends(get_session)):
    
    vehicle = db.get(VehicleType,vehicle_id)
    if vehicle is None:
        raise HTTPException(
            status_code=404,
            details="Vehicle not found!"
        )
    db.delete(vehicle)
    db.commit()
    return {
        "message": f"{vehicle.vehicle_type} was deleted."
    }

# ==================================================================================

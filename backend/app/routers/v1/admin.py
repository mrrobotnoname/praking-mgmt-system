from fastapi import APIRouter


router=APIRouter(
    prefix="/api/v1/admin"
)


@router.get("/")
def admin():
    return "welcom to the admin"
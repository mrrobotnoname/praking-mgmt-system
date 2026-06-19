from fastapi import FastAPI
from app.db.session import init_db
from app.routers.v1 import auth,admin

app = FastAPI()



@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return "Bingo"

app.include_router(auth.router,prefix="/api/v1/auth")
app.include_router(admin.router)


    
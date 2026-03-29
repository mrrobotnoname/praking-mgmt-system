import _asyncio
from fastapi import FastAPI
from contextlib import contextmanager



@contextmanager
async def lifespan(app: FastAPI):
    print("Loading the Model")
    ## Model logic here
    yield
    print("sutting down")

app = FastAPI(lifespan=lifespan)

    
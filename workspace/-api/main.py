from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.routers import auth
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "Login API is running"}

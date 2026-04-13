"""Deep Vision by DNS — API Server."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, cameras, events, zones, recordings, health, alerts, snapshots, persons


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    redirect_slashes=False,
    title="Deep Vision by DNS",
    description="Video analytics platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api")
app.include_router(cameras.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(recordings.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")
app.include_router(persons.router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Deep Vision by DNS", "version": "1.0.0", "status": "running"}

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, booking, bookings, chat, kb, notifications, tickets
from app.config import settings
from app.db.database import Base, engine
from app.db.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    yield


app = FastAPI(title="Servora API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(analytics.router)
app.include_router(kb.router)
app.include_router(booking.router)
app.include_router(bookings.router)
app.include_router(notifications.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

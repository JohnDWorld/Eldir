"""Router WebSocket - agrégateur."""

from fastapi import APIRouter

from app.ws.sessions import router as sessions_ws_router

ws_router = APIRouter()
ws_router.include_router(sessions_ws_router)

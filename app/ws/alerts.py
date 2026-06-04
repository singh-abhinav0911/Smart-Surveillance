from fastapi import APIRouter, WebSocket
from core.shared_state import SharedState
import asyncio

router = APIRouter()
shared_state = SharedState()

@router.websocket("/ws/alerts")
async def alerts_socket(ws: WebSocket):
    await ws.accept()

    last = 0

    while True:
        if len(shared_state.alerts) > last:
            await ws.send_json(shared_state.alerts[last:])
            last = len(shared_state.alerts)

        await asyncio.sleep(0.5)
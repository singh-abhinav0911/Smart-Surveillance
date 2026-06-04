# app/ws/events_ws.py — replace entire file

import json
import asyncio
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    print("[WS] client connected")

    try:
        r = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("events")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        print("[WS] client disconnected")
    except Exception as e:
        print(f"[WS] error: {e}")
    finally:
        await pubsub.unsubscribe("events")
        await r.aclose()
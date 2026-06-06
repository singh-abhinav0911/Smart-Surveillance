# app/ws/events_ws.py — replace entire file

import json
import asyncio
import redis.asyncio as aioredis
from utils.logger import get_logger
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log = get_logger("events_ws")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    log.info("client connected")

    try:
        r = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("events")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        log.info("client disconnected")
    except Exception as e:
        log.error(f"error: {e}")
    finally:
        await pubsub.unsubscribe("events")
        await r.aclose()
"""
WebSocket Route Handlers
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from uuid import uuid4

from langtrader_api.websocket.manager import ws_manager
from langtrader_api.schemas.websocket import WSMessage, WSEventType, WSCommand
from langtrader_api.config import settings

router = APIRouter()


@router.websocket("/trading/{bot_id}")
async def trading_websocket(
    websocket: WebSocket,
    bot_id: int,
    token: str = Query(..., alias="api_key", description="API Key for authentication"),
):
    """
    WebSocket endpoint for real-time trading updates
    
    Connect with: ws://localhost:8000/ws/trading/{bot_id}?api_key=your-key
    
    Auto-subscribes to:
    - bot:{bot_id}:status
    - bot:{bot_id}:trades
    - bot:{bot_id}:decisions
    - bot:{bot_id}:cycles
    
    Commands:
    - {"action": "subscribe", "channel": "system:alerts"}
    - {"action": "unsubscribe", "channel": "system:alerts"}
    - {"action": "ping"}
    """
    # Validate API key
    if token not in settings.API_KEYS:
        await websocket.close(code=4001, reason="Invalid API Key")
        return
    
    connection_id = f"bot_{bot_id}_{uuid4().hex[:8]}"
    
    await ws_manager.connect(websocket, connection_id, token)
    
    # Auto-subscribe to bot channels
    await ws_manager.subscribe(connection_id, f"bot:{bot_id}:status")
    await ws_manager.subscribe(connection_id, f"bot:{bot_id}:trades")
    await ws_manager.subscribe(connection_id, f"bot:{bot_id}:decisions")
    await ws_manager.subscribe(connection_id, f"bot:{bot_id}:cycles")
    
    # Notify subscriptions
    await ws_manager.send_personal(connection_id, WSMessage(
        event=WSEventType.SUBSCRIBED,
        data={
            "channels": [
                f"bot:{bot_id}:status",
                f"bot:{bot_id}:trades",
                f"bot:{bot_id}:decisions",
                f"bot:{bot_id}:cycles",
            ]
        }
    ))
    
    try:
        while True:
            # Receive commands from client
            data = await websocket.receive_json()
            
            try:
                command = WSCommand(**data)
            except Exception:
                await ws_manager.send_personal(connection_id, WSMessage(
                    event=WSEventType.ERROR,
                    data={"message": "Invalid command format"}
                ))
                continue
            
            if command.action == "subscribe":
                if command.channel:
                    await ws_manager.subscribe(connection_id, command.channel)
                    await ws_manager.send_personal(connection_id, WSMessage(
                        event=WSEventType.SUBSCRIBED,
                        data={"channel": command.channel}
                    ))
            
            elif command.action == "unsubscribe":
                if command.channel:
                    await ws_manager.unsubscribe(connection_id, command.channel)
                    await ws_manager.send_personal(connection_id, WSMessage(
                        event=WSEventType.UNSUBSCRIBED,
                        data={"channel": command.channel}
                    ))
            
            elif command.action == "ping":
                await ws_manager.send_personal(connection_id, WSMessage(
                    event=WSEventType.PONG,
                    data={}
                ))
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(connection_id)
    except Exception:
        await ws_manager.disconnect(connection_id)


@router.websocket("/system")
async def system_websocket(
    websocket: WebSocket,
    token: str = Query(..., alias="api_key", description="API Key"),
):
    """
    WebSocket endpoint for system-wide updates
    
    Auto-subscribes to:
    - system:alerts
    """
    # Validate API key
    if token not in settings.API_KEYS:
        await websocket.close(code=4001, reason="Invalid API Key")
        return
    
    connection_id = f"system_{uuid4().hex[:8]}"
    
    await ws_manager.connect(websocket, connection_id, token)
    await ws_manager.subscribe(connection_id, "system:alerts")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            try:
                command = WSCommand(**data)
            except Exception:
                continue
            
            if command.action == "ping":
                await ws_manager.send_personal(connection_id, WSMessage(
                    event=WSEventType.PONG,
                    data={}
                ))
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(connection_id)
    except Exception:
        await ws_manager.disconnect(connection_id)


@router.get("/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return ws_manager.get_stats()


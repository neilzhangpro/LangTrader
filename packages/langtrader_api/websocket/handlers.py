"""
WebSocket Route Handlers

安全说明：
- API Key 不再通过 URL 参数传递（避免日志泄露）
- 连接后需发送认证消息: {"action": "auth", "api_key": "xxx"}
- 认证超时时间为 30 秒
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from uuid import uuid4
from typing import Optional

from langtrader_api.websocket.manager import ws_manager
from langtrader_api.schemas.websocket import WSMessage, WSEventType, WSCommand
from langtrader_api.config import settings

router = APIRouter()

# 认证超时时间（秒）
AUTH_TIMEOUT = 30


async def authenticate_websocket(websocket: WebSocket, connection_id: str) -> bool:
    """
    等待客户端发送认证消息
    
    期望格式: {"action": "auth", "api_key": "your-api-key"}
    
    Returns:
        True if authenticated, False otherwise
    """
    try:
        # 等待认证消息，设置超时
        data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=AUTH_TIMEOUT
        )
        
        action = data.get("action")
        api_key = data.get("api_key")
        
        if action != "auth":
            await ws_manager.send_personal(connection_id, WSMessage(
                event=WSEventType.ERROR,
                data={"message": "First message must be auth: {\"action\": \"auth\", \"api_key\": \"xxx\"}"}
            ))
            return False
        
        if not api_key or api_key not in settings.API_KEYS:
            await ws_manager.send_personal(connection_id, WSMessage(
                event=WSEventType.ERROR,
                data={"message": "Invalid API Key"}
            ))
            return False
        
        # 认证成功
        await ws_manager.send_personal(connection_id, WSMessage(
            event=WSEventType.CONNECTED,
            data={"message": "Authenticated successfully", "connection_id": connection_id}
        ))
        return True
        
    except asyncio.TimeoutError:
        await ws_manager.send_personal(connection_id, WSMessage(
            event=WSEventType.ERROR,
            data={"message": f"Authentication timeout ({AUTH_TIMEOUT}s)"}
        ))
        return False
    except Exception as e:
        await ws_manager.send_personal(connection_id, WSMessage(
            event=WSEventType.ERROR,
            data={"message": f"Authentication error: {str(e)}"}
        ))
        return False


@router.websocket("/trading/{bot_id}")
async def trading_websocket(
    websocket: WebSocket,
    bot_id: int,
    # 保留旧参数以兼容，但标记为可选（deprecated）
    token: Optional[str] = Query(None, alias="api_key", description="[DEPRECATED] Use auth message instead"),
):
    """
    WebSocket endpoint for real-time trading updates
    
    ## 连接方式（新版，推荐）:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/trading/1');
    ws.onopen = () => {
        ws.send(JSON.stringify({action: "auth", api_key: "your-key"}));
    };
    ```
    
    ## 连接方式（旧版，已废弃）:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/trading/1?api_key=xxx');
    ```
    
    Auto-subscribes to:
    - bot:{bot_id}:status
    - bot:{bot_id}:trades
    - bot:{bot_id}:decisions
    - bot:{bot_id}:cycles
    
    Commands:
    - {"action": "auth", "api_key": "xxx"} - 认证（必须首先发送）
    - {"action": "subscribe", "channel": "system:alerts"}
    - {"action": "unsubscribe", "channel": "system:alerts"}
    - {"action": "ping"}
    """
    connection_id = f"bot_{bot_id}_{uuid4().hex[:8]}"
    
    # 接受连接（不验证，等待认证消息）
    await ws_manager.connect(websocket, connection_id, api_key="pending")
    
    # 兼容旧版：如果 URL 中有 token，直接验证（但记录警告）
    if token and token in settings.API_KEYS:
        # 旧版兼容模式 - 发送弃用警告
        await ws_manager.send_personal(connection_id, WSMessage(
            event=WSEventType.CONNECTED,
            data={
                "message": "Connected (deprecated URL auth)",
                "warning": "URL-based authentication is deprecated. Please use message-based auth.",
                "connection_id": connection_id
            }
        ))
        authenticated = True
    elif token:
        # 无效的 token
        await websocket.close(code=4001, reason="Invalid API Key")
        return
    else:
        # 新版：等待认证消息
        authenticated = await authenticate_websocket(websocket, connection_id)
        if not authenticated:
            await ws_manager.disconnect(connection_id)
            await websocket.close(code=4001, reason="Authentication failed")
            return
    
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
            
            # 忽略认证后的 auth 命令
            if command.action == "auth":
                await ws_manager.send_personal(connection_id, WSMessage(
                    event=WSEventType.ERROR,
                    data={"message": "Already authenticated"}
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
    token: Optional[str] = Query(None, alias="api_key", description="[DEPRECATED] Use auth message instead"),
):
    """
    WebSocket endpoint for system-wide updates
    
    ## 连接方式（新版，推荐）:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/system');
    ws.onopen = () => {
        ws.send(JSON.stringify({action: "auth", api_key: "your-key"}));
    };
    ```
    
    Auto-subscribes to:
    - system:alerts
    """
    connection_id = f"system_{uuid4().hex[:8]}"
    
    await ws_manager.connect(websocket, connection_id, api_key="pending")
    
    # 兼容旧版
    if token and token in settings.API_KEYS:
        await ws_manager.send_personal(connection_id, WSMessage(
            event=WSEventType.CONNECTED,
            data={
                "message": "Connected (deprecated URL auth)",
                "warning": "URL-based authentication is deprecated.",
                "connection_id": connection_id
            }
        ))
        authenticated = True
    elif token:
        await websocket.close(code=4001, reason="Invalid API Key")
        return
    else:
        authenticated = await authenticate_websocket(websocket, connection_id)
        if not authenticated:
            await ws_manager.disconnect(connection_id)
            await websocket.close(code=4001, reason="Authentication failed")
            return
    
    await ws_manager.subscribe(connection_id, "system:alerts")
    
    await ws_manager.send_personal(connection_id, WSMessage(
        event=WSEventType.SUBSCRIBED,
        data={"channels": ["system:alerts"]}
    ))
    
    try:
        while True:
            data = await websocket.receive_json()
            
            try:
                command = WSCommand(**data)
            except Exception:
                continue
            
            if command.action == "auth":
                await ws_manager.send_personal(connection_id, WSMessage(
                    event=WSEventType.ERROR,
                    data={"message": "Already authenticated"}
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


@router.get("/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return ws_manager.get_stats()

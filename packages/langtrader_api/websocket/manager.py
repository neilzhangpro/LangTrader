"""
WebSocket Connection Manager
Handles real-time updates for trading data
"""
from fastapi import WebSocket
from typing import Dict, Set, List, Any
from dataclasses import dataclass, field
import asyncio
import json

from langtrader_api.schemas.websocket import WSMessage, WSEventType


@dataclass
class ConnectionInfo:
    """WebSocket connection metadata"""
    websocket: WebSocket
    api_key: str
    subscriptions: Set[str] = field(default_factory=set)


class WSManager:
    """
    WebSocket Connection Manager
    
    Manages connections and message broadcasting.
    
    Channels:
    - bot:{bot_id}:status     - Bot status updates
    - bot:{bot_id}:trades     - Trade executions
    - bot:{bot_id}:decisions  - AI decisions
    - bot:{bot_id}:cycles     - Cycle completions
    - system:alerts           - System-wide alerts
    """
    
    def __init__(self):
        self._connections: Dict[str, ConnectionInfo] = {}
        self._channels: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(
        self, 
        websocket: WebSocket, 
        connection_id: str,
        api_key: str
    ):
        """Accept new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            self._connections[connection_id] = ConnectionInfo(
                websocket=websocket,
                api_key=api_key
            )
        
        # Send welcome message
        await self.send_personal(connection_id, WSMessage(
            event=WSEventType.CONNECTED,
            data={"connection_id": connection_id}
        ))
    
    async def disconnect(self, connection_id: str):
        """Handle disconnection"""
        async with self._lock:
            if connection_id in self._connections:
                # Remove from all channels
                info = self._connections[connection_id]
                for channel in info.subscriptions:
                    if channel in self._channels:
                        self._channels[channel].discard(connection_id)
                
                del self._connections[connection_id]
    
    async def subscribe(self, connection_id: str, channel: str):
        """Subscribe connection to a channel"""
        async with self._lock:
            if connection_id not in self._connections:
                return False
            
            if channel not in self._channels:
                self._channels[channel] = set()
            
            self._channels[channel].add(connection_id)
            self._connections[connection_id].subscriptions.add(channel)
            return True
    
    async def unsubscribe(self, connection_id: str, channel: str):
        """Unsubscribe from a channel"""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].subscriptions.discard(channel)
            
            if channel in self._channels:
                self._channels[channel].discard(connection_id)
    
    async def send_personal(self, connection_id: str, message: WSMessage):
        """Send message to specific connection"""
        if connection_id not in self._connections:
            return False
        
        try:
            await self._connections[connection_id].websocket.send_json(
                message.model_dump(mode='json')
            )
            return True
        except Exception:
            await self.disconnect(connection_id)
            return False
    
    async def broadcast_channel(self, channel: str, message: WSMessage):
        """Broadcast message to all subscribers of a channel"""
        if channel not in self._channels:
            return
        
        message.channel = channel
        dead_connections = []
        
        for conn_id in self._channels[channel].copy():
            if conn_id in self._connections:
                try:
                    await self._connections[conn_id].websocket.send_json(
                        message.model_dump(mode='json')
                    )
                except Exception:
                    dead_connections.append(conn_id)
        
        # Cleanup dead connections
        for conn_id in dead_connections:
            await self.disconnect(conn_id)
    
    async def broadcast_all(self, message: WSMessage):
        """Broadcast to all connections"""
        dead_connections = []
        
        for conn_id, info in list(self._connections.items()):
            try:
                await info.websocket.send_json(message.model_dump(mode='json'))
            except Exception:
                dead_connections.append(conn_id)
        
        for conn_id in dead_connections:
            await self.disconnect(conn_id)
    
    def get_connection_count(self) -> int:
        """Get total number of connections"""
        return len(self._connections)
    
    def get_channel_subscribers(self, channel: str) -> int:
        """Get number of subscribers for a channel"""
        return len(self._channels.get(channel, set()))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket statistics"""
        return {
            "total_connections": len(self._connections),
            "channels": {
                channel: len(subs) 
                for channel, subs in self._channels.items()
            }
        }


# Global instance
ws_manager = WSManager()


# =============================================================================
# Helper functions for broadcasting from other parts of the application
# =============================================================================

async def broadcast_bot_status(bot_id: int, status_data: dict):
    """Broadcast bot status update"""
    await ws_manager.broadcast_channel(
        f"bot:{bot_id}:status",
        WSMessage(
            event=WSEventType.BOT_STARTED if status_data.get("is_running") else WSEventType.BOT_STOPPED,
            data=status_data
        )
    )


async def broadcast_trade_executed(bot_id: int, trade_data: dict):
    """Broadcast trade execution"""
    await ws_manager.broadcast_channel(
        f"bot:{bot_id}:trades",
        WSMessage(
            event=WSEventType.TRADE_EXECUTED,
            data=trade_data
        )
    )


async def broadcast_decision_made(bot_id: int, decision_data: dict):
    """Broadcast AI decision"""
    await ws_manager.broadcast_channel(
        f"bot:{bot_id}:decisions",
        WSMessage(
            event=WSEventType.DECISION_MADE,
            data=decision_data
        )
    )


async def broadcast_cycle_completed(bot_id: int, cycle_data: dict):
    """Broadcast cycle completion"""
    await ws_manager.broadcast_channel(
        f"bot:{bot_id}:cycles",
        WSMessage(
            event=WSEventType.CYCLE_COMPLETED,
            data=cycle_data
        )
    )


async def broadcast_system_alert(message: str, level: str = "info"):
    """Broadcast system-wide alert"""
    await ws_manager.broadcast_channel(
        "system:alerts",
        WSMessage(
            event=WSEventType.ALERT,
            data={"message": message, "level": level}
        )
    )


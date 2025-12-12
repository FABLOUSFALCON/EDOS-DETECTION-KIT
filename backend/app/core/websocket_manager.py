"""
WebSocket Connection Manager for real-time communication
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Any
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for different channels"""

    def __init__(self):
        # Store connections by channel type - now supports dynamic resource-specific channels
        self.active_connections: Dict[str, List[WebSocket]] = {
            "alerts": [],
            "metrics": [],
            "network_traffic": [],
            "logs": [],
            "threat_map": [],  # Default threat map
        }
        # Resource-specific channels will be created dynamically: threat_map_{resource_id}

    async def connect(self, websocket: WebSocket, channel: str):
        """Connect a client to a specific channel"""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(
            f"Client connected to {channel} channel. Total: {len(self.active_connections[channel])}"
        )

    def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect a client from a channel"""
        if channel in self.active_connections:
            try:
                self.active_connections[channel].remove(websocket)
                logger.info(
                    f"Client disconnected from {channel} channel. Total: {len(self.active_connections[channel])}"
                )
            except ValueError:
                pass

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to a specific client"""
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, channel: str, data: Any):
        """Broadcast message to all clients in a channel"""
        if channel not in self.active_connections:
            return

        message = json.dumps(data, default=str)
        disconnected_clients = []

        for connection in self.active_connections[channel]:
            try:
                # Check if connection is still active before sending
                if connection.client_state.name != "DISCONNECTED":
                    await connection.send_text(message)
                else:
                    disconnected_clients.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to {channel}: {e}")
                disconnected_clients.append(connection)

        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client, channel)

    async def broadcast_to_room(self, channel: str, data: Any):
        """Broadcast message to all clients in a specific room/channel"""
        await self.broadcast(channel, data)

    def get_connection_count(self, channel: str) -> int:
        """Get number of active connections for a channel"""
        return len(self.active_connections.get(channel, []))

    def get_all_connection_counts(self) -> Dict[str, int]:
        """Get connection counts for all channels"""
        return {
            channel: len(connections)
            for channel, connections in self.active_connections.items()
        }


# Global websocket manager instance
websocket_manager = ConnectionManager()

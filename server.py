import asyncio
import websockets
import json
import subprocess
import os
import re
from tabulate import tabulate
from threading import Thread
import threading

SERVER_HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))
connected_clients = {}
clients_cwd = {}
current_client = None

class RenderServer:
    def __init__(self):
        print(f"🚀 Starting WebSocket Server on port {PORT}")
        print("✅ Render.com Compatible")
        print("📡 Waiting for connections...")
    
    async def handle_client(self, websocket, path):
        """Handle incoming WebSocket connections"""
        client_id = id(websocket)
        print(f"🔗 New connection: {client_id}")
        
        # Get initial directory
        cwd = os.getcwd()
        connected_clients[client_id] = websocket
        clients_cwd[client_id] = cwd
        
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": f"Connected to Render Server. CWD: {cwd}",
            "cwd": cwd
        }))
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_command(websocket, client_id, data)
                
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Connection closed: {client_id}")
        finally:
            if client_id in connected_clients:
                del connected_clients[client_id]
                del clients_cwd[client_id]
    
    async def process_command(self, websocket, client_id, data):
        """Process commands from client"""
        command = data.get("command", "")
        cwd = clients_cwd.get(client_id, os.getcwd())
        
        print(f"📥 Command from {client_id}: {command}")
        
        if command.lower() in ["exit", "quit"]:
            await websocket.send(json.dumps({
                "type": "output",
                "output": "Disconnecting...",
                "cwd": cwd
            }))
            await websocket.close()
            
        elif command.lower() == "list":
            # List all connected clients
            client_list = []
            for cid, ws in connected_clients.items():
                client_list.append([cid, clients_cwd.get(cid, "Unknown")])
            
            output = tabulate(client_list, headers=["ID", "CWD"])
            await websocket.send(json.dumps({
                "type": "output",
                "output": output,
                "cwd": cwd
            }))
            
        elif command.startswith("use "):
            # Select a client (simplified for demo)
            await websocket.send(json.dumps({
                "type": "output",
                "output": f"Selected client for commands",
                "cwd": cwd
            }))
            
        elif command.startswith("cd "):
            # Change directory
            try:
                path = command[3:].strip()
                if path:
                    os.chdir(path)
                    cwd = os.getcwd()
                    clients_cwd[client_id] = cwd
                    output = f"Changed directory to: {cwd}"
                else:
                    output = "Please specify a path"
            except Exception as e:
                output = f"Error: {str(e)}"
            
            await websocket.send(json.dumps({
                "type": "output",
                "output": output,
                "cwd": cwd
            }))
            
        else:
            # Execute system command
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=10
                )
                output = result.stdout
                if result.stderr:
                    output += f"\nError: {result.stderr}"
                    
                # Update CWD after command
                cwd = os.getcwd()
                clients_cwd[client_id] = cwd
                
            except subprocess.TimeoutExpired:
                output = "Command timed out"
            except Exception as e:
                output = f"Error: {str(e)}"
            
            await websocket.send(json.dumps({
                "type": "output",
                "output": output,
                "cwd": cwd
            }))
    
    async def start(self):
        """Start the WebSocket server"""
        async with websockets.serve(self.handle_client, SERVER_HOST, PORT):
            print(f"✅ Server running on ws://0.0.0.0:{PORT}")
            print("🌐 Render URL: https://render-reverse-shel.onrender.com")
            await asyncio.Future()  # Run forever

def main():
    server = RenderServer()
    asyncio.run(server.start())

if __name__ == "__main__":
    main()
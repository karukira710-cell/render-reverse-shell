import asyncio
import websockets
import json
import subprocess
import os
import re
from tabulate import tabulate
import http.server
import socketserver
import threading

SERVER_HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))
connected_clients = {}
clients_cwd = {}

# Simple HTTP server for Render health checks
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Reverse Shell Server is Running</h1><p>WebSocket endpoint: ws://" + self.headers.get('Host', '').encode() + b"/ws</p>")
        elif self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    """Start simple HTTP server for Render health checks"""
    handler = HealthCheckHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"✅ HTTP Server running on port {PORT}")
        httpd.serve_forever()

class RenderServer:
    def __init__(self):
        print(f"🚀 Starting WebSocket Server")
        print("✅ Render.com Compatible")
    
    async def handle_client(self, websocket, path):
        """Handle incoming WebSocket connections"""
        client_id = str(id(websocket))
        print(f"🔗 New WebSocket connection: {client_id}")
        
        # Get initial directory
        cwd = os.getcwd()
        connected_clients[client_id] = websocket
        clients_cwd[client_id] = cwd
        
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": f"Connected! Your ID: {client_id}",
            "cwd": cwd
        }))
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_command(websocket, client_id, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "output": "Invalid JSON format"
                    }))
                
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
        
        if not command.strip():
            return
        
        print(f"📥 Command: {command[:50]}...")
        
        if command.lower() in ["exit", "quit"]:
            await websocket.send(json.dumps({
                "type": "output",
                "output": "Goodbye!",
                "cwd": cwd
            }))
            await websocket.close()
            return
            
        elif command.lower() == "list":
            output = "Connected clients:\n"
            for cid, cwd in clients_cwd.items():
                output += f"- {cid}: {cwd}\n"
            
        elif command.startswith("cd "):
            try:
                path = command[3:].strip()
                if path:
                    os.chdir(path)
                    cwd = os.getcwd()
                    clients_cwd[client_id] = cwd
                    output = f"Changed to: {cwd}"
                else:
                    output = "Usage: cd <path>"
            except Exception as e:
                output = f"Error: {str(e)}"
            
        else:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30
                )
                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"
                    
                cwd = os.getcwd()
                clients_cwd[client_id] = cwd
                
            except subprocess.TimeoutExpired:
                output = "Command timed out (30s)"
            except Exception as e:
                output = f"Error: {str(e)}"
        
        await websocket.send(json.dumps({
            "type": "output",
            "output": output,
            "cwd": cwd
        }))
    
    async def start_websocket(self):
        """Start WebSocket server on different port"""
        ws_port = PORT + 1 if PORT < 65535 else 8081
        async with websockets.serve(self.handle_client, SERVER_HOST, ws_port):
            print(f"✅ WebSocket running on ws://0.0.0.0:{ws_port}")
            await asyncio.Future()

def main():
    server = RenderServer()
    
    # Start HTTP server in background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Start WebSocket server in main thread
    asyncio.run(server.start_websocket())

if __name__ == "__main__":
    main()

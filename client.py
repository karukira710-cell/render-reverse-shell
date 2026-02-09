import asyncio
import websockets
import json
import sys
import os
import subprocess
import ssl

class RenderClient:
    def __init__(self, server_url):
        # Convert Render URL to WebSocket
        if "onrender.com" in server_url:
            server_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
        
        if not server_url.startswith("ws"):
            server_url = f"wss://{server_url}"
        
        # Use port 10001 for WebSocket (HTTP is 10000)
        if ":" not in server_url.split("//")[1]:
            server_url = server_url.replace("onrender.com", "onrender.com:10001")
        
        self.server_url = server_url
        print(f"🔗 Connecting to: {self.server_url}")
    
    async def run(self):
        # SSL context for wss://
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            async with websockets.connect(self.server_url, ssl=ssl_context) as websocket:
                print("✅ Connected!")
                
                # Get welcome message
                welcome = await websocket.recv()
                data = json.loads(welcome)
                print(f"Server: {data.get('message', '')}")
                cwd = data.get("cwd", "~")
                
                while True:
                    # Get command input
                    cmd = input(f"\n{cwd} $> ").strip()
                    
                    if not cmd:
                        continue
                    
                    if cmd.lower() in ["exit", "quit"]:
                        await websocket.send(json.dumps({"command": "exit"}))
                        break
                    
                    # Send command
                    await websocket.send(json.dumps({"command": cmd}))
                    
                    # Get response
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if data.get("type") == "output":
                        print(data.get("output", ""))
                        cwd = data.get("cwd", cwd)
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            print("\nTrying alternative connection method...")
            await self.try_alternative()

    async def try_alternative(self):
        """Try connecting without SSL"""
        alt_url = self.server_url.replace("wss://", "ws://")
        print(f"Trying: {alt_url}")
        
        try:
            async with websockets.connect(alt_url) as websocket:
                print("✅ Connected (without SSL)!")
                await websocket.send(json.dumps({"command": "pwd"}))
                response = await websocket.recv()
                print(f"Response: {response}")
        except Exception as e:
            print(f"❌ Still failed: {e}")
            print("\n🎯 Quick Fix: Use this command instead:")
            print(f"python simple_client.py {self.server_url.replace('wss://', '').replace('ws://', '').split(':')[0]}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <render-url>")
        print("Example: python client.py your-app.onrender.com")
        print("Example: python client.py https://your-app.onrender.com")
        sys.exit(1)
    
    # Simple connection test
    server_url = sys.argv[1]
    
    # For Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    client = RenderClient(server_url)
    asyncio.run(client.run())

if __name__ == "__main__":
    main()

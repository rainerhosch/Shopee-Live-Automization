import asyncio
import websockets

async def main():
    try:
        ws = await websockets.connect('ws://127.0.0.1:22222/', open_timeout=5, close_timeout=2)
        print("Connected with timeouts!")
        await ws.close()
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(main())

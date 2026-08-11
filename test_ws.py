import asyncio
import websockets

async def main():
    try:
        ws = await websockets.connect('ws://127.0.0.1:22222/')
        print("Connected:", type(ws))
        await ws.close()
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(main())

import asyncio
import sys
from backend.app.panda_client import PandaClient

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    p = PandaClient()
    try:
        await p.connect()
        print("PandaClient connected successfully!")
        devices = await p.list_devices()
        print("Devices:", devices)
        await p.close()
    except Exception as e:
        print("Error connecting PandaClient:", repr(e))

asyncio.run(main())

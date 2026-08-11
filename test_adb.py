import asyncio
from backend.app.device_manager import device_manager

async def main():
    try:
        await device_manager.connect()
        print("Connected!")
        devices = await device_manager.list_devices()
        print("Devices:", devices)
        await device_manager.close()
    except Exception as e:
        print("Error:", e)

asyncio.run(main())

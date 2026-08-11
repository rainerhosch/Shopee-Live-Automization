@echo off
echo ==============================================
echo Building Shopee Live Bot Desktop Executable...
echo ==============================================

:: Activating virtual environment
call .venv\Scripts\activate

:: Run PyInstaller with necessary hidden imports
pyinstaller --noconfirm --onedir --windowed --name "ShopeeBot" ^
  --hidden-import uvicorn.loops ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols ^
  --hidden-import uvicorn.protocols.http ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan.on ^
  --hidden-import uvicorn.lifespan.off ^
  --hidden-import fastapi ^
  --hidden-import pydantic ^
  --hidden-import starlette ^
  --hidden-import anyio ^
  --add-data "backend/static;backend/static" ^
  desktop.py

echo.
echo ==============================================
echo Build finished! Check the "dist\ShopeeBot" folder.
echo ==============================================
pause

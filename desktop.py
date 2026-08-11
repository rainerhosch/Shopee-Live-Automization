import sys
import threading
import time
import os
import multiprocessing

def start_server():
    import uvicorn
    from backend.app.main import app
    # Run Uvicorn in the background thread. We don't need reload in production.
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def on_closed():
    # Force exit the process when the UI window is closed
    os._exit(0)

if __name__ == '__main__':
    # Required when using multiprocessing in a frozen PyInstaller executable
    multiprocessing.freeze_support()
    
    # Must import webview here to ensure freeze_support is called first
    import webview
    
    # Start the FastAPI server in a background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Give the server a moment to start before opening the UI
    time.sleep(1.5)
    
    # Create the Desktop GUI Window pointing to our local server
    window = webview.create_window(
        'Shopee Live Bot',
        'http://127.0.0.1:8000',
        width=1280,
        height=800,
        min_size=(900, 600)
    )
    
    # Attach event so closing the window stops the backend
    window.events.closed += on_closed
    
    # Start the webview loop
    webview.start(private_mode=False)

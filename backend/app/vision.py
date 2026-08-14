import xml.etree.ElementTree as ET
import asyncio
import re
from typing import Tuple, Optional
import io
import time
from .logger import log_bus

async def get_screen_bytes(adb_client) -> Optional[bytes]:
    """
    Mengambil raw screenshot dari adb menggunakan perintah efisien `exec-out screencap -p`.
    """
    try:
        # Gunakan private method untuk raw bytes
        code, stdout, stderr = await adb_client._run_adb_bytes("exec-out", "screencap", "-p")
        if code == 0 and len(stdout) > 0:
            return stdout
    except Exception as e:
        await log_bus.error(f"Screencap error: {e}")
    return None

async def dump_ui(adb_client, device_id: str) -> Optional[ET.Element]:
    """
    Mengekstrak Android UI-Tree (XML) menggunakan uiautomator.
    """
    try:
        args_dump = ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"]
        args_cat = ["shell", "cat", "/sdcard/window_dump.xml"]
        if device_id:
            args_dump = ["-s", device_id] + args_dump
            args_cat = ["-s", device_id] + args_cat
            
        await adb_client._run_adb(*args_dump)
        code, xml_bytes, _ = await adb_client._run_adb_bytes(*args_cat)
        if code == 0:
            return ET.fromstring(xml_bytes.decode('utf-8'))
    except Exception as e:
        await log_bus.error(f"UI Dump error: {e}")
    return None

def find_node_by_text(root: ET.Element, text: str) -> Optional[dict]:
    """
    Mencari node yang memiliki text atau content-desc sesuai dengan target (case-insensitive & partial match).
    """
    if root is None:
        return None
    
    target = text.lower()
    # BFS traversal
    queue = [root]
    while queue:
        node = queue.pop(0)
        node_text = node.attrib.get('text', '').lower()
        node_desc = node.attrib.get('content-desc', '').lower()
        
        if target in node_text or target in node_desc:
            bounds_str = node.attrib.get('bounds')
            if bounds_str:
                # Format: [x1,y1][x2,y2]
                bounds_str = bounds_str.replace('][', ',').replace('[', '').replace(']', '')
                x1, y1, x2, y2 = map(int, bounds_str.split(','))
                return {
                    "text": node.attrib.get('text', ''),
                    "desc": node.attrib.get('content-desc', ''),
                    "bounds": (x1, y1, x2, y2),
                    "center": (x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2)
                }
        for child in node:
            queue.append(child)
            
    return None

def find_all_nodes_by_regex(root: ET.Element, pattern: str) -> list[dict]:
    """
    Mencari semua node yang memiliki text atau content-desc sesuai dengan regex pattern.
    """
    if root is None:
        return []
    
    prog = re.compile(pattern, re.IGNORECASE)
    results = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        node_text = node.attrib.get('text', '')
        node_desc = node.attrib.get('content-desc', '')
        
        if prog.search(node_text) or prog.search(node_desc):
            bounds_str = node.attrib.get('bounds')
            if bounds_str:
                bounds_str = bounds_str.replace('][', ',').replace('[', '').replace(']', '')
                x1, y1, x2, y2 = map(int, bounds_str.split(','))
                results.append({
                    "text": node_text,
                    "desc": node_desc,
                    "bounds": (x1, y1, x2, y2),
                    "center": (x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2)
                })
        for child in node:
            queue.append(child)
            
    return results

def find_node_by_regex(root: ET.Element, pattern: str) -> Optional[dict]:
    """
    Mencari node yang memiliki text atau content-desc sesuai dengan regex pattern.
    """
    if root is None:
        return None
    
    prog = re.compile(pattern, re.IGNORECASE)
    queue = [root]
    while queue:
        node = queue.pop(0)
        node_text = node.attrib.get('text', '')
        node_desc = node.attrib.get('content-desc', '')
        
        if prog.search(node_text) or prog.search(node_desc):
            bounds_str = node.attrib.get('bounds')
            if bounds_str:
                bounds_str = bounds_str.replace('][', ',').replace('[', '').replace(']', '')
                x1, y1, x2, y2 = map(int, bounds_str.split(','))
                return {
                    "text": node_text,
                    "desc": node_desc,
                    "bounds": (x1, y1, x2, y2),
                    "center": (x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2)
                }
        for child in node:
            queue.append(child)
            
    return None

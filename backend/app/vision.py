import xml.etree.ElementTree as ET
import asyncio
import re
from typing import Tuple, Optional
import io
import time
import cv2
import numpy as np
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

def find_dynamic_icon(screen_img, icon_name: str):
    """
    Finds the exact X, Y percentage of the action bar icons dynamically using peak detection.
    Lainnya = rightmost (-1)
    Iklan = 2nd rightmost (-2)
    Lelang = 3rd rightmost (-3)
    """
    try:
        screen_h, screen_w = screen_img.shape[:2]
        # Potong hanya area bawah tempat action bar berada (misal 70% ke bawah)
        crop_y_start = int(screen_h * 0.7)
        crop_y_end = int(screen_h * 0.95)
        bottom_region = screen_img[crop_y_start:crop_y_end, :]

        # Konversi ke grayscale dan threshold untuk mencari blob putih (ikon)
        if len(bottom_region.shape) == 3:
            gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = bottom_region
            
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Jumlahkan piksel putih secara vertikal untuk mencari kolom dengan ikon
        col_sums = np.sum(thresh, axis=0)
        
        # Smooth grafik untuk menghilangkan noise kecil
        kernel_size = max(5, int(screen_w * 0.01))
        smooth = np.convolve(col_sums, np.ones(kernel_size)/kernel_size, mode='same')
        
        # Gunakan scipy untuk mencari puncak (ikon)
        from scipy.signal import find_peaks
        distance = int(screen_w * 0.1) # Jarak minimal antar ikon ~10% layar
        peaks, _ = find_peaks(smooth, distance=distance, height=np.max(smooth) * 0.1)
        
        if len(peaks) < 3:
            return None # Gagal mendeteksi deretan ikon

        target_idx = -1
        if "lainnya" in icon_name.lower():
            target_idx = -1
        elif "iklan" in icon_name.lower():
            target_idx = -2
        elif "lelang" in icon_name.lower():
            target_idx = -3
        else:
            return None
            
        cx = peaks[target_idx]
        
        # Untuk Y, ambil tengah dari area crop yang ada piksel putihnya
        row_sums = np.sum(thresh[:, max(0, cx-20):min(screen_w, cx+20)], axis=1)
        y_peaks, _ = find_peaks(row_sums, distance=10, height=np.max(row_sums) * 0.1)
        if len(y_peaks) > 0:
            cy = crop_y_start + y_peaks[0]
        else:
            cy = crop_y_start + (crop_y_end - crop_y_start) // 2

        return {
            "bounds": (cx-25, cy-25, cx+25, cy+25),
            "center": (cx, cy),
            "center_pct": (round(cx / screen_w * 100, 2), round(cy / screen_h * 100, 2)),
            "confidence": 1.0 # 100% yakin karena lokasinya absolut matematis
        }
    except Exception:
        return None

def find_image_on_screen(screen_bytes: bytes, template_path: str, threshold: float = 0.8) -> Optional[dict]:
    """
    Mencari lokasi template gambar pada screenshot menggunakan Edge Detection (Canny)
    sehingga kebal terhadap perubahan background video Shopee Live.
    Mencari HANYA di 40% bagian bawah layar untuk menghindari false positive.
    """
    try:
        np_arr = np.frombuffer(screen_bytes, np.uint8)
        screen_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if screen_img is None:
            return None

        # [AUTOMATION OVERRIDE] 
        # Jika user mencari tombol spesifik Shopee Live, gunakan logika deteksi dinamis
        # yang jauh lebih akurat dan kebal terhadap perubahan device/resolusi!
        dynamic_match = find_dynamic_icon(screen_img, template_path)
        if dynamic_match:
            return dynamic_match

        template_img = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template_img is None:
            return None

        # 1. Batasi pencarian ke 40% bagian bawah layar
        screen_h, screen_w = screen_img.shape[:2]
        crop_y_start = int(screen_h * 0.6) # Mulai dari 60% layar ke bawah
        screen_cropped = screen_img[crop_y_start:screen_h, 0:screen_w]

        # 2. Convert ke Grayscale
        screen_gray = cv2.cvtColor(screen_cropped, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

        # 3. Kita tidak perlu Edge Detection (Canny) karena backgroundnya hitam pekat.
        # Langsung cocokkan gambar Grayscale agar membedakan isi ikon dengan akurat.
        best_max_val = -1
        best_max_loc = None
        best_scale = 1.0
        best_w, best_h = 0, 0

        # Kita membatasi scale dari 0.8 ke 1.2.
        # JANGAN gunakan scale besar (seperti 4.0) karena pada background hitam pekat,
        # template yang diperbesar akan mendominasi skor kecocokan dengan pixel hitam
        # yang berujung pada pergeseran titik tengah (center X/Y).
        for scale in np.linspace(0.8, 1.2, 9)[::-1]:
            resized_template = cv2.resize(template_gray, (0, 0), fx=scale, fy=scale)
            if resized_template.shape[0] > screen_gray.shape[0] or resized_template.shape[1] > screen_gray.shape[1]:
                continue
            
            res = cv2.matchTemplate(screen_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val > best_max_val:
                best_max_val = max_val
                best_max_loc = max_loc
                best_scale = scale
                best_h, best_w = resized_template.shape[:2]

        if best_max_val >= threshold:
            x1, y1 = best_max_loc
            y1 += crop_y_start 
            x2, y2 = x1 + best_w, y1 + best_h
            cx = x1 + best_w // 2
            cy = y1 + best_h // 2
            
            return {
                "bounds": (x1, y1, x2, y2),
                "center": (cx, cy),
                "center_pct": (round(cx / screen_w * 100, 2), round(cy / screen_h * 100, 2)),
                "confidence": best_max_val
            }
        
        # Jika threshold gagal atau sangat rendah (sebagai debug)
        if best_max_val < 0.7:
            try:
                cv2.imwrite("backend/templates/debug_screenshot_failed.png", screen_img)
            except Exception:
                pass

        return {
            "bounds": (0, 0, 0, 0),
            "center": (0, 0),
            "center_pct": (0.0, 0.0),
            "confidence": best_max_val
        }

    except Exception as e:
        import logging
        logging.error(f"Error in find_image_on_screen: {e}")

    return None

def find_node_by_text(root: ET.Element, text: str) -> Optional[dict]:
    """
    Mencari node yang memiliki text atau content-desc sesuai dengan target (case-insensitive & partial match).
    """
    if root is None:
        return None
    
    target = text.lower()
    best_match = None
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
                match_data = {
                    "text": node.attrib.get('text', ''),
                    "desc": node.attrib.get('content-desc', ''),
                    "bounds": (x1, y1, x2, y2),
                    "center": (x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2)
                }
                # Prefer exact match
                if target == node_text or target == node_desc:
                    return match_data
                # Save first partial match as fallback
                if not best_match:
                    best_match = match_data
                    
        for child in node:
            queue.append(child)
            
    return best_match

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

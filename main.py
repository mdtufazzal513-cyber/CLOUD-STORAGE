from fastapi import FastAPI, UploadFile, File, Request, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pyrogram import Client
import os
import traceback
import re
import asyncio
import urllib.parse
import json
import shutil
import uuid
import hashlib
from pydantic import BaseModel
from typing import List
import firebase_admin
from firebase_admin import credentials, auth as fb_auth, db as fb_db

# --- Firebase Admin SDK Setup (Ultra Pro Level & Auto-Fixing) ---
try:
    import json
    import textwrap

    with open("firebase-adminsdk.json", "r", encoding="utf-8") as f:
        cert_dict = json.load(f)
    
    # 🚨 ULTIMATE PRIVATE KEY FIXER 🚨
    # কপি-পেস্ট বা অপারেটিং সিস্টেমের কারণে Key-এর ভেতরের স্পেস বা লাইন ব্রেক নষ্ট হলে এটি নিজে থেকে ফিক্স করে নেবে!
    raw_key = cert_dict.get("private_key", "")
    
    # সব ধরণের লাইন ব্রেক ও স্পেস রিমুভ করে একদম ক্লিন করা হচ্ছে
    clean_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
    clean_key = clean_key.replace("\\n", "").replace("\n", "").replace("\r", "").replace(" ", "")
    
    # স্ট্যান্ডার্ড PEM ফরম্যাটে (৬৪ ক্যারেক্টার পর পর লাইন ব্রেক) নতুন করে সাজানো হচ্ছে
    formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(textwrap.wrap(clean_key, 64)) + "\n-----END PRIVATE KEY-----\n"
    cert_dict["private_key"] = formatted_key

    cred = credentials.Certificate(cert_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://file-to-stream-default-rtdb.asia-southeast1.firebasedatabase.app'
    })
    print("✅ Firebase Admin SDK Initialized Perfectly!")
except Exception as e:
    print(f"❌ Failed to initialize Firebase Admin SDK: {e}")

class BulkDeleteRequest(BaseModel):
    message_ids: List[int]

# সার্ভারের ওপর চাপ কমানোর জন্য ট্রাফিক কন্ট্রোলার (Android Download Manager multiple thread support)
MAX_CONCURRENT_DOWNLOADS = 15
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

app = FastAPI()

# --- CORS পলিসি সেটআপ (খুবই গুরুত্বপূর্ণ) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # যেকোনো ওয়েবসাইট থেকে রিকোয়েস্ট গ্রহণ করবে
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, DELETE সব এলাউ করবে
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"], # ফাইল ডাউনলোডের জন্য এটি অত্যন্ত জরুরি
    max_age=3600 # ব্রাউজার ১ ঘণ্টার জন্য সিকিউরিটি চেক ক্যাশ করে রাখবে (স্পিড বুস্ট)
)

# Central Config File (generate_session.py) থেকে ডাটা ইম্পোর্ট করা হচ্ছে
import generate_session as config

API_ID = config.API_ID
API_HASH = config.API_HASH
SESSION_STRING = config.SESSION_STRING
CHANNEL_ID = config.CHANNEL_ID

# Pyrogram Client Setup
bot = Client("my_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
async def startup():
    print("--- Starting Telegram Session... ---")
    await bot.start()
    try:
        async for dialog in bot.get_dialogs(limit=100):
            pass
        print("--- Dialogs Loaded Successfully! ---")
    except Exception as e:
        print("Error loading dialogs:", e)

@app.on_event("shutdown")
async def shutdown():
    await bot.stop()

@app.get("/")
async def root():
    return {"status": "Cloud Storage API is Running successfully!"}

@app.get("/ping")
async def ping_server():
    return {"status": "awake"}

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        safe_filename = file.filename.replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        file_size = 0
        
        # Free Server Protection: RAM বাঁচানোর জন্য ফাইলটি 1MB করে ছোট ছোট খণ্ডে (Chunk) সেভ করা হচ্ছে
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) # 1 MB chunk
                if not chunk:
                    break
                buffer.write(chunk)
                file_size += len(chunk)

        # Pyrogram ফাইলটিকে টেলিগ্রামে আপলোড করবে (এটি ডিফল্টভাবেই স্মার্ট স্ট্রিমিং ব্যবহার করে)
        sent_message = await bot.send_document(chat_id=CHANNEL_ID, document=file_path)
        
        if os.path.exists(file_path):
            os.remove(file_path)

        return {"status": "success", "file_name": file.filename, "file_size": file_size, "message_id": sent_message.id}

    except Exception as e:
        print(f"!!! UPLOAD ERROR: {e} !!!")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

# --- Resumable Download System (Pause/Resume Support) ---
@app.get("/download/{message_id}/{file_name:path}")
async def download_file(message_id: int, file_name: str, request: Request):
    try:
        message = await bot.get_messages(CHANNEL_ID, message_id)
        
        # মেসেজ ডিলিট হয়ে গেলে বা ফাইল না থাকলে
        if not message or getattr(message, "empty", False) or (not getattr(message, "document", None) and not getattr(message, "video", None) and not getattr(message, "photo", None)):
            return JSONResponse(status_code=404, content={"error": "File not found or deleted from Telegram"})

        media = message.document or message.video or message.photo
        
        # ফিক্স: ইউজার যে রিনেম করা নাম পাঠিয়েছে সেটাই যেন ইউজ হয়, টেলিগ্রামের পুরোনো নাম যেন না বসে।
        if not file_name or file_name.strip() == "":
            file_name = getattr(media, "file_name", f"file_{message_id}")
            
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "application/octet-stream")

        if file_size == 0:
            return JSONResponse(status_code=400, content={"error": "File size is 0 bytes (corrupted upload)"})

        range_header = request.headers.get("Range")
        start = 0
        end = file_size - 1
        status_code = 200

        if range_header:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end_str = range_match.group(2)
                end = int(end_str) if end_str else file_size - 1
                status_code = 206 

        # ফিক্স: ব্রোকেন পাইপ এরর চিরতরে দূর করার জন্য ফুল-প্রুফ স্ট্যান্ডার্ড এনকোডিং (ASCII + UTF-8)
        safe_ascii_name = file_name.encode('ascii', 'ignore').decode('ascii').replace('"', '').replace('\n', '')
        if not safe_ascii_name:
            safe_ascii_name = f"file_{message_id}"
            
        encoded_name = urllib.parse.quote(file_name)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f'attachment; filename="{safe_ascii_name}"; filename*=utf-8\'\'{encoded_name}'
        }

        # Pyrogram থেকে নির্দিষ্ট বাইট (offset) থেকে স্ট্রিম করা
        async def ranged_file_streamer():
            async with download_semaphore: 
                try:
                    async for chunk in bot.stream_media(message, offset=start, limit=(end - start + 1)):
                        if await request.is_disconnected():
                            print("User canceled the download. Releasing slot...")
                            break
                        yield chunk
                except asyncio.CancelledError:
                    print("Download task was canceled by browser. Slot freed.")
                except Exception as e:
                    print(f"Stream interrupted: {e}")

        return StreamingResponse(ranged_file_streamer(), status_code=status_code, headers=headers, media_type=mime_type)

    except Exception as e:
        print(f"Download Error: {e}")
        return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})

@app.post("/prepare-zip")
async def prepare_zip_folder(folder_name: str = Form(...), files_data: str = Form(...)):
    try:
        files = json.loads(files_data)
        if not files:
            return JSONResponse(status_code=400, content={"error": "No files found to zip"})
            
        # Free Server Protection: 500 MB এর বেশি হলে জিপ বাতিল করা হবে
        total_size_bytes = sum(f.get("file_size", 0) for f in files)
        MAX_ZIP_SIZE = 500 * 1024 * 1024 # 500 MB
        
        if total_size_bytes > MAX_ZIP_SIZE:
            return JSONResponse(status_code=400, content={
                "error": "Folder is too large (>500MB) to ZIP. Please open the folder and download files individually."
            })
        
        # স্মার্ট ক্যাশিং: ফাইলের লিস্ট থেকে একটি ইউনিক হ্যাশ (MD5) তৈরি করা হচ্ছে
        payload_hash = hashlib.md5(files_data.encode('utf-8')).hexdigest()
        
        # ফিক্স ১: ফোল্ডারের নামে স্পেস বা স্পেশাল ক্যারেক্টার থাকলে লিনাক্স ডিরেক্টরি এরর দেয়, তাই সেফ নাম তৈরি করা হলো
        safe_folder_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', folder_name)
        unique_id = f"{safe_folder_name}_{payload_hash}"
        
        base_dir = os.path.abspath(UPLOAD_DIR)
        zip_filename = f"{folder_name}.zip"
        zip_filepath = os.path.join(base_dir, f"temp_zip_{unique_id}.zip")
        
        encoded_name = urllib.parse.quote(zip_filename)

        # যদি এই ফোল্ডারের (একই ফাইলের) জিপ আগে থেকেই রেডি থাকে, তবে সার্ভার জিপ না বানিয়ে ডাইরেক্ট লিংক দিয়ে দেবে
        if os.path.exists(zip_filepath):
            return JSONResponse(status_code=200, content={
                "status": "ready", 
                "download_url": f"/download-ready-zip/{unique_id}/{encoded_name}"
            })
            
        # যদি আগে থেকে রেডি না থাকে বা ফোল্ডারে নতুন ফাইল যোগ হয়, তবে নতুন করে জিপ বানাবে
        temp_dir = os.path.join(base_dir, f"temp_folder_{unique_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        for f in files:
            msg_id = int(f.get("message_id")) 
            file_name = f.get("file_name")
            path = f.get("path", "")
            
            message = await bot.get_messages(CHANNEL_ID, msg_id)
            if message and not getattr(message, "empty", False):
                
                # ফিক্স ২: ফাইলের নামে স্ল্যাশ (/) থাকলে সেটি ভুল ডিরেক্টরিতে চলে যাওয়ার চেষ্টা করে, তাই basename ব্যবহার করা হলো
                safe_file_name = os.path.basename(file_name)
                save_dir = os.path.join(temp_dir, path)
                os.makedirs(save_dir, exist_ok=True)
                
                save_path = os.path.abspath(os.path.join(save_dir, safe_file_name))
                
                # ফিক্স ৩: কোনো একটি ফাইল ডাউনলোড ফেইল করলে পুরো জিপ প্রসেস যেন ক্র্যাশ না করে, সেটির প্রোটেকশন
                try:
                    await bot.download_media(message, file_name=save_path)
                except Exception as e:
                    print(f"Skipping file {safe_file_name} due to error: {e}")
                    continue
        
        # ফিক্স: জিপ তৈরির কাজটিকে Background Thread-এ পাঠানো হলো, যাতে সার্ভার ল্যাগ না করে এবং অন্য ইউজাররা স্মুথলি ১ জিবির মুভি ডাউনলোড/আপলোড করতে পারে।
        await asyncio.to_thread(shutil.make_archive, zip_filepath.replace('.zip', ''), 'zip', temp_dir)
        
        # স্টোরেজ বাঁচাতে র (Raw) ফাইলগুলো সাথে সাথে ডিলিট করে দেওয়া হলো
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
        # সার্ভার চাপমুক্ত রাখতে ১০ মিনিট (৬০০ সেকেন্ড) পর জিপ ফাইলটিও অটোমেটিক ডিলিট হবে
        async def delete_later():
            await asyncio.sleep(600)
            if os.path.exists(zip_filepath):
                os.remove(zip_filepath)
        asyncio.create_task(delete_later())
        
        encoded_name = urllib.parse.quote(zip_filename)
        return JSONResponse(status_code=200, content={
            "status": "ready", 
            "download_url": f"/download-ready-zip/{unique_id}/{encoded_name}"
        })
        
    except Exception as e:
        print(f"Zip Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download-ready-zip/{zip_id}/{file_name:path}")
async def download_ready_zip(zip_id: str, file_name: str):
    zip_filepath = os.path.join(UPLOAD_DIR, f"temp_zip_{zip_id}.zip")
    
    if not os.path.exists(zip_filepath):
        return JSONResponse(status_code=404, content={"error": "ZIP file expired or not found"})
        
    # Download Manager সাপোর্ট করার জন্য FileResponse রিটার্ন করা হচ্ছে
    return FileResponse(
        path=zip_filepath, 
        filename=urllib.parse.unquote(file_name), 
        media_type="application/zip",
        headers={"Accept-Ranges": "bytes"}
    )

@app.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    try:
        await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=message_id)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- নতুন: প্রফেশনাল Bulk Delete (Background Task) ---
async def delete_messages_in_background(message_ids: list):
    # টেলিগ্রাম একসাথে ১০০টি মেসেজ ডিলিট করতে দেয়, তাই ১০০ করে ভাগ (chunk) করা হলো
    chunk_size = 100
    for i in range(0, len(message_ids), chunk_size):
        chunk = message_ids[i:i + chunk_size]
        try:
            await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=chunk)
            await asyncio.sleep(1) # ফ্লাড-ওয়েট এড়াতে ১ সেকেন্ড ডিলে
        except Exception as e:
            print(f"Bulk delete error: {e}")

@app.post("/bulk-delete")
async def bulk_delete_files(request_data: BulkDeleteRequest, background_tasks: BackgroundTasks):
    if not request_data.message_ids:
        return {"status": "success", "message": "No files to delete"}
    
    # ব্রাউজারকে সাথে সাথে রেসপন্স দিয়ে ব্যাকগ্রাউন্ডে ডিলিট প্রসেস শুরু করা হলো
    background_tasks.add_task(delete_messages_in_background, request_data.message_ids)
    
    return {"status": "success", "message": f"Started deleting {len(request_data.message_ids)} files in background"}
# --- Admin Panel এর জন্য Central Verification API ---
@app.get("/get-admin-config")
async def get_admin_config():
    return {"admin_uids": config.ADMIN_UIDS}

# --- Pro-Level Account Deletion API (Prevents Ghost Accounts & Saves DB Read/Writes) ---
class DeleteAccountRequest(BaseModel):
    uid: str
    message_ids: List[int]

@app.post("/delete-account")
async def delete_account_api(req: DeleteAccountRequest, background_tasks: BackgroundTasks):
    try:
        # 1. Background Task: Telegram থেকে ফাইল ডিলিট করা
        if req.message_ids:
            background_tasks.add_task(delete_messages_in_background, req.message_ids)
            
        # 2. Server-side DB Wipe: Firebase ডাটাবেস থেকে ইউজারের পুরো হিস্ট্রি ডিলিট করা
        # সার্ভার থেকে ডিলিট করার কারণে ক্লায়েন্ট সাইডের onDisconnect ট্র্যাকার ট্রিগার হবে না।
        fb_db.reference(f"users/{req.uid}").delete()
        
        # 3. Server-side Auth Wipe: Firebase Auth থেকে ইউজারকে ডিলিট করা
        try:
            fb_auth.delete_user(req.uid)
        except Exception as e:
            print(f"Auth User already deleted or error: {e}")
            
        return {"status": "success", "message": "Account wiped cleanly from server"}
    except Exception as e:
        print(f"Server Deletion Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

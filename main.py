from fastapi import FastAPI, UploadFile, File, Request, Form, BackgroundTasks, Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
import time
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

from typing import List, Any
class BulkDeleteRequest(BaseModel):
    message_ids: List[Any]

# সার্ভারের ওপর চাপ কমানোর জন্য ট্রাফিক কন্ট্রোলার (Android Download Manager multiple thread support)
MAX_CONCURRENT_DOWNLOADS = 15
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

app = FastAPI()

# --- Firebase Token Verification Security ---
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        # ফায়ারবেস থেকে টোকেন চেক করে ইউজারের ভ্যালিডিটি নিশ্চিত করা হচ্ছে
        decoded_token = fb_auth.verify_id_token(credentials.credentials)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or Expired Firebase Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

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

# --- Environment Variables (.env) থেকে ডাটা ইম্পোর্ট করা হচ্ছে ---
from dotenv import load_dotenv
import os

load_dotenv() # লোকাল পিসির জন্য .env লোড করবে

# Bootstrapping Variables (Fallback)
ENV_API_ID = int(os.environ.get("API_ID", 0))
ENV_API_HASH = os.environ.get("API_HASH", "")
ENV_SESSION_STRING = os.environ.get("SESSION_STRING", "")
ENV_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
ADMIN_UIDS = os.environ.get("ADMIN_UIDS", "")

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🚨 Server RAM Protection (Active Task Counter)
active_tasks = 0
MAX_ACTIVE_TASKS = 6 # ফ্রি সার্ভারের জন্য একসাথে ৬টি রিকোয়েস্ট নিরাপদ

# --- 🚀 Smart Telegram Cluster Manager ---
class TelegramCluster:
    def __init__(self):
        self.clients = []
        self.primary_channel = 0
        self.backup_channels = []
        self.current_client_index = 0
        self.is_ready = False

    async def reload_config(self):
        try:
            config_ref = fb_db.reference('system_settings/telegram_config').get()
            
            api_id = int(config_ref.get('api_id', ENV_API_ID)) if config_ref else ENV_API_ID
            api_hash = config_ref.get('api_hash', ENV_API_HASH) if config_ref else ENV_API_HASH
            
            sessions_str = config_ref.get('sessions', ENV_SESSION_STRING) if config_ref else ENV_SESSION_STRING
            sessions = [s.strip() for s in sessions_str.split(',') if s.strip()]
            
            channels_str = config_ref.get('channels', str(ENV_CHANNEL_ID)) if config_ref else str(ENV_CHANNEL_ID)
            channels = [int(c.strip()) for c in channels_str.split(',') if c.strip()]

            if not sessions or not channels:
                print("⚠️ Telegram Config Missing!")
                return

            self.primary_channel = channels[0]
            self.backup_channels = channels[1:]

            for client in self.clients:
                try: await client.stop()
                except: pass
            self.clients.clear()

            for idx, session in enumerate(sessions):
                client = Client(f"session_{idx}", api_id=api_id, api_hash=api_hash, session_string=session, in_memory=True)
                await client.start()
                self.clients.append(client)
            
            self.is_ready = True
            print(f"✅ Telegram Cluster Ready: {len(self.clients)} Sessions, 1 Primary, {len(self.backup_channels)} Backups.")
        except Exception as e:
            print(f"❌ Cluster Boot Error: {e}")

    def get_next_client(self):
        if not self.clients: return None
        client = self.clients[self.current_client_index]
        self.current_client_index = (self.current_client_index + 1) % len(self.clients)
        return client

tg_cluster = TelegramCluster()

class BotProxy:
    def __getattr__(self, item):
        client = tg_cluster.get_next_client()
        if not client: raise Exception("No clients available")
        return getattr(client, item)

bot = BotProxy()
CHANNEL_ID = 0 # To be overridden dynamically in code

# --- Auto-Trash Cleaner (Background Job) ---
async def auto_trash_cleaner():
    TRASH_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000 # 30 Days in MS
    await asyncio.sleep(60) # সার্ভার স্টার্ট হওয়ার ৬০ সেকেন্ড পর প্রথমবার রান করবে
    while True:
        try:
            print("🧹 Running Auto-Trash Background Cleaner...")
            users_ref = fb_db.reference('users')
            users = users_ref.get()
            if users:
                now_ms = int(time.time() * 1000)
                for uid, user_data in users.items():
                    updates = {}
                    message_ids_to_delete = []

                    # চেক ফোল্ডারস
                    folders = user_data.get('folders', {})
                    for f_key, f_data in folders.items():
                        if f_data.get('is_trashed'):
                            trashed_at = f_data.get('trashed_at', 0)
                            if (now_ms - trashed_at) > TRASH_EXPIRY_MS:
                                updates[f'users/{uid}/folders/{f_key}'] = None

                    # চেক ফাইলস
                    files = user_data.get('files', {})
                    for f_key, f_data in files.items():
                        if f_data.get('is_trashed'):
                            trashed_at = f_data.get('trashed_at', 0)
                            if (now_ms - trashed_at) > TRASH_EXPIRY_MS:
                                updates[f'users/{uid}/files/{f_key}'] = None
                                if f_data.get('message_id'):
                                    message_ids_to_delete.append(int(f_data['message_id']))

                    # একসাথে টেলিগ্রাম থেকে ডিলিট করা
                    if message_ids_to_delete:
                        for i in range(0, len(message_ids_to_delete), 100):
                            chunk = message_ids_to_delete[i:i + 100]
                            try:
                                await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=chunk)
                                await asyncio.sleep(1)
                            except Exception as e:
                                pass

                    # ফায়ারবেস থেকে মুছে ফেলা
                    if updates:
                        fb_db.reference().update(updates)
                        print(f"✅ Cleared expired trash for user: {uid}")
                        
        except Exception as e:
            print(f"❌ Auto-Trash Error: {e}")
        
        # প্রতি ১২ ঘণ্টা পর পর চেক করবে (সার্ভার রিলাক্স থাকবে)
        await asyncio.sleep(12 * 60 * 60)

# সার্ভার চালুর সময় আগের টেম্পোরারি ফাইলগুলো মুছে সার্ভার ক্লিন করা হচ্ছে (Storage Leak Fix)
def cleanup_temp_folder():
    try:
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        print("🧹 Temp folder cleaned up successfully on startup!")
    except Exception as e:
        print(f"Error cleaning temp folder: {e}")

@app.on_event("startup")
async def startup():
    cleanup_temp_folder() 
    
    try:
        admin_uids_str = ADMIN_UIDS
        if admin_uids_str:
            admin_list = [uid.strip() for uid in admin_uids_str.split(",")]
            admin_updates = {uid: True for uid in admin_list if uid}
            fb_db.reference('admins').set(admin_updates)
            print("👑 Admin UIDs automatically synced to Firebase Database!")
    except Exception as e:
        print(f"Error syncing admins: {e}")

    print("--- Starting Telegram Cluster... ---")
    await tg_cluster.reload_config()
    
    asyncio.create_task(auto_trash_cleaner())

@app.on_event("shutdown")
async def shutdown():
    for client in tg_cluster.clients:
        try: await client.stop()
        except: pass

@app.get("/")
async def root():
    return {"status": "Cloud Storage API is Running successfully!"}

@app.get("/ping")
async def ping_server():
    return {"status": "awake"}

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), user_token: dict = Depends(verify_token)):
    global active_tasks
    if active_tasks >= MAX_ACTIVE_TASKS:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Server is under heavy load. Please wait a moment and try again."})
    
    active_tasks += 1
    try:
        if not tg_cluster.is_ready:
            return JSONResponse(status_code=500, content={"status": "error", "message": "Cluster not ready yet!"})

        try:
            maintenance_ref = fb_db.reference('system_settings/maintenance_mode')
            m_data = maintenance_ref.get()
            if m_data and isinstance(m_data, dict):
                if m_data.get('status') == 'active':
                    return JSONResponse(status_code=403, content={"status": "error", "message": "Server is in maintenance mode!"})
        except Exception: pass

        try:
            max_size_ref = fb_db.reference('system_settings/max_file_size')
            MAX_ALLOWED_SIZE = max_size_ref.get()
            if not MAX_ALLOWED_SIZE: MAX_ALLOWED_SIZE = 500 * 1024 * 1024
        except Exception: MAX_ALLOWED_SIZE = 500 * 1024 * 1024

        safe_filename = f"{uuid.uuid4().hex}_{file.filename.replace(' ', '_')}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        file_size = 0
        
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) 
                if not chunk: break
                buffer.write(chunk)
                file_size += len(chunk)
                if file_size > MAX_ALLOWED_SIZE:
                    buffer.close()
                    os.remove(file_path)
                    return JSONResponse(status_code=400, content={"status": "error", "message": f"Upload aborted! Exceeds limit."})

        # ১. ডাইনামিক সেশন বাছাই করা
        client = tg_cluster.get_next_client()
        if not client: raise Exception("No Telegram sessions available!")

        # ২. প্রাইমারি চ্যানেলে আপলোড
        sent_message = await client.send_document(chat_id=tg_cluster.primary_channel, document=file_path)
        
        msg_ids = { "primary": sent_message.id, "backups": [] }

        # ৩. ব্যাকআপ চ্যানেলগুলোতে ফরোয়ার্ড করা (Magic Trick!)
        for backup_id in tg_cluster.backup_channels:
            try:
                fw_msg = await client.forward_messages(chat_id=backup_id, from_chat_id=tg_cluster.primary_channel, message_ids=sent_message.id)
                msg_ids["backups"].append({"channel": backup_id, "msg_id": fw_msg.id})
            except Exception as e:
                print(f"Forwarding to backup {backup_id} failed: {e}")

        import json
        message_id_payload = json.dumps(msg_ids)

        return {"status": "success", "file_name": file.filename, "file_size": file_size, "message_id": message_id_payload}

    except Exception as e:
        print(f"!!! UPLOAD ERROR: {e} !!!")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
        
    finally:
        active_tasks -= 1
        if 'file_path' in locals() and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

# --- Resumable Download System (Pause/Resume Support) ---
@app.get("/download/{message_id}/{file_name:path}")
async def download_file(message_id: str, file_name: str, request: Request):
    global active_tasks
    if active_tasks >= MAX_ACTIVE_TASKS:
        return JSONResponse(status_code=503, content={"error": "Server is busy. Please wait a moment."})
    
    active_tasks += 1
    try:
        client = tg_cluster.get_next_client()
        if not client: raise Exception("No Telegram sessions available!")

        # Parse new multi-channel payload (JSON) and fallback legacy ID
        targets = []
        try:
            payload = json.loads(urllib.parse.unquote(message_id))
            targets.append((tg_cluster.primary_channel, payload.get("primary")))
            for b in payload.get("backups", []):
                targets.append((b["channel"], b["msg_id"]))
        except Exception:
            targets.append((tg_cluster.primary_channel, int(message_id)))

        message = None
        for chat_id, msg_id in targets:
            try:
                msg = await client.get_messages(chat_id, msg_id)
                if msg and not getattr(msg, "empty", False) and (msg.document or msg.video or msg.photo):
                    message = msg
                    break # Found valid message!
            except Exception: continue

        if not message:
            return JSONResponse(status_code=404, content={"error": "File not found in any cloud channels"})

        media = message.document or message.video or message.photo
        if not file_name or file_name.strip() == "": file_name = getattr(media, "file_name", f"file_{message.id}")
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "application/octet-stream")

        if file_size == 0: return JSONResponse(status_code=400, content={"error": "File size is 0 bytes"})

        range_header = request.headers.get("Range")
        start = 0; end = file_size - 1; status_code = 200
        if range_header:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end_str = range_match.group(2)
                end = int(end_str) if end_str else file_size - 1
                status_code = 206 

        safe_ascii_name = file_name.encode('ascii', 'ignore').decode('ascii').replace('"', '').replace('\n', '')
        if not safe_ascii_name: safe_ascii_name = f"file_{message.id}"
        encoded_name = urllib.parse.quote(file_name)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f'attachment; filename="{safe_ascii_name}"; filename*=utf-8\'\'{encoded_name}'
        }

        async def ranged_file_streamer():
            async with download_semaphore: 
                try:
                    async for chunk in client.stream_media(message, offset=start, limit=(end - start + 1)):
                        if await request.is_disconnected(): break
                        yield chunk
                except asyncio.CancelledError: pass
                except Exception as e: print(f"Stream interrupted: {e}")

        return StreamingResponse(ranged_file_streamer(), status_code=status_code, headers=headers, media_type=mime_type)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Internal Error: {str(e)}"})
    finally:
        active_tasks -= 1

@app.post("/prepare-zip")
async def prepare_zip_folder(folder_name: str = Form(...), files_data: str = Form(...), user_token: dict = Depends(verify_token)):
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
        
        client = tg_cluster.get_next_client()
        for f in files:
            raw_msg_id = str(f.get("message_id")) 
            file_name = f.get("file_name")
            path = f.get("path", "")
            
            targets = []
            try:
                payload = json.loads(urllib.parse.unquote(raw_msg_id))
                targets.append((tg_cluster.primary_channel, payload.get("primary")))
                for b in payload.get("backups", []):
                    targets.append((b["channel"], b["msg_id"]))
            except Exception:
                targets.append((tg_cluster.primary_channel, int(raw_msg_id)))

            message = None
            for chat_id, m_id in targets:
                try:
                    msg = await client.get_messages(chat_id, m_id)
                    if msg and not getattr(msg, "empty", False):
                        message = msg
                        break
                except Exception: continue
            
            if message:
                safe_file_name = os.path.basename(file_name)
                save_dir = os.path.join(temp_dir, path)
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.abspath(os.path.join(save_dir, safe_file_name))
                try:
                    await client.download_media(message, file_name=save_path)
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
async def delete_file(message_id: str, user_token: dict = Depends(verify_token)):
    try:
        to_delete = {}
        try:
            payload = json.loads(urllib.parse.unquote(message_id))
            p_chat = tg_cluster.primary_channel
            to_delete[p_chat] = [payload.get("primary")]
            for b in payload.get("backups", []):
                b_chat = b["channel"]
                if b_chat not in to_delete: to_delete[b_chat] = []
                to_delete[b_chat].append(b["msg_id"])
        except Exception:
            to_delete[tg_cluster.primary_channel] = [int(message_id)]

        client = tg_cluster.get_next_client()
        for chat_id, ids in to_delete.items():
            try: await client.delete_messages(chat_id=chat_id, message_ids=ids)
            except Exception: pass
            
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Professional Bulk Delete (Multi-Channel) ---
async def delete_messages_in_background(message_ids: list):
    to_delete = {} 
    for item in message_ids:
        try:
            payload = json.loads(str(item))
            p_chat = tg_cluster.primary_channel
            if p_chat not in to_delete: to_delete[p_chat] = []
            to_delete[p_chat].append(payload.get("primary"))
            
            for b in payload.get("backups", []):
                b_chat = b["channel"]
                if b_chat not in to_delete: to_delete[b_chat] = []
                to_delete[b_chat].append(b["msg_id"])
        except Exception:
            p_chat = tg_cluster.primary_channel
            if p_chat not in to_delete: to_delete[p_chat] = []
            try: to_delete[p_chat].append(int(item))
            except: pass

    client = tg_cluster.get_next_client()
    if not client: return

    for chat_id, ids in to_delete.items():
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            try:
                await client.delete_messages(chat_id=chat_id, message_ids=chunk)
                await asyncio.sleep(1) 
            except Exception: pass

@app.post("/bulk-delete")
async def bulk_delete_files(request_data: BulkDeleteRequest, background_tasks: BackgroundTasks, user_token: dict = Depends(verify_token)):
    try:
        maintenance_ref = fb_db.reference('system_settings/maintenance_mode')
        m_data = maintenance_ref.get()
        if m_data and isinstance(m_data, dict):
            if m_data.get('status') == 'active':
                return JSONResponse(status_code=403, content={"status": "error", "message": "Server is under maintenance!"})
    except Exception: pass

    msg_ids = getattr(request_data, 'message_ids', [])
    if not msg_ids: return {"status": "success"}
    
    background_tasks.add_task(delete_messages_in_background, msg_ids)
    return {"status": "success", "message": f"Deleting {len(msg_ids)} files"}

# --- Admin Panel APIs ---
@app.get("/get-admin-config")
async def get_admin_config():
    return {"admin_uids": ADMIN_UIDS}

@app.post("/reload-telegram-cluster")
async def reload_telegram_cluster(user_token: dict = Depends(verify_token)):
    try:
        uid = user_token.get("uid")
        is_admin = fb_db.reference(f'admins/{uid}').get()
        if not is_admin: return JSONResponse(status_code=403, content={"error": "Admin only"})
        
        await tg_cluster.reload_config()
        return {"status": "success", "message": "Cluster reloaded successfully!"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Server-side Delete API has been removed. 
# Deletion is now handled directly via Client-side Firebase SDK to prevent server errors.

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pyrogram import Client
import os
import traceback
import re
import asyncio
import urllib.parse

# সার্ভারের স্পিড বুস্ট করার জন্য ট্রাফিক কন্ট্রোলার (Max 5 concurrent downloads)
MAX_CONCURRENT_DOWNLOADS = 5
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

# Render-এর Environment Variable
API_ID = int(os.getenv("API_ID", "33445387"))
API_HASH = os.getenv("API_HASH", "5b1badf6d0f44c940a2263cef28d6689").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "BQH-VgsAjXAtpA7_8WzYjaImZMmoFJUd6RFEut4X32b15iWR-62IjLNTLZQt1xYigp13Sm6rcUVvXEuUdpoJDhwkaSTOCcT2CWGtRPslhvdY7JueDWhne_rJtCSqoV0AcADg21xCGuDNjLl4LaIry4VQerxgYEOmD93djo0MPUZRxoHuEAcNxTrCxr_IqC6fzEsMxB5Mqk1nnNM_-ZBsNKSzfvCiCljgVktNXXilhmchvLTFXs2EvYSHewxyJRuTK-NAVupaUKywQE1hVNWKMmJNKdIbXdPzGFbITV4wdY54ezBTsd1pP-NfLGb_VJYUkaQmeEy5EP49-Ak8gSkZL4AbrMqFKAAAAAIE58I1AA").strip()
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003984468691"))

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
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            file_size = len(content)

        sent_message = await bot.send_document(chat_id=CHANNEL_ID, document=file_path)
        
        if os.path.exists(file_path):
            os.remove(file_path)

        # Firebase-এ ডাটা সেভ করার জন্য শুধু ইনফরমেশন রিটার্ন করছি।
        return {"status": "success", "file_name": file.filename, "file_size": file_size, "message_id": sent_message.id}

    except Exception as e:
        print(f"!!! UPLOAD ERROR: {e} !!!")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

# --- Resumable Download System (Pause/Resume Support) ---
@app.get("/download/{message_id}/{file_name}")
async def download_file(message_id: int, file_name: str, request: Request):
    try:
        message = await bot.get_messages(CHANNEL_ID, message_id)
        
        # মেসেজ ডিলিট হয়ে গেলে বা ফাইল না থাকলে
        if not message or getattr(message, "empty", False) or (not getattr(message, "document", None) and not getattr(message, "video", None) and not getattr(message, "photo", None)):
            return JSONResponse(status_code=404, content={"error": "File not found or deleted from Telegram"})

        media = message.document or message.video or message.photo
        file_name = getattr(media, "file_name", f"file_{message_id}")
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "application/octet-stream")

        # ফাইল জিরো বাইট হলে সার্ভার যেন ক্র্যাশ না করে
        if file_size == 0:
            return JSONResponse(status_code=400, content={"error": "File size is 0 bytes (corrupted upload)"})

        # Range Header লজিক (Pause/Resume এর জন্য)
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
                status_code = 206 # Partial Content

        # ফাইলের নামে স্পেস, ইমোজি বা বাংলা থাকলে সার্ভার ক্র্যাশ (500 Error) করে, তাই এটি এনকোড করা হলো
        encoded_name = urllib.parse.quote(file_name)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}"
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

@app.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    try:
        await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=message_id)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

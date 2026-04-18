from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pyrogram import Client
import sqlite3
import os

app = FastAPI()

# Render-এর Environment Variable থেকে ডাটা নিবে এবং .strip() দিয়ে অতিরিক্ত স্পেস মুছে ফেলবে
API_ID = int(os.getenv("API_ID", "33445387"))
API_HASH = os.getenv("API_HASH", "5b1badf6d0f44c940a2263cef28d6689").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781052287:AAEYTaE5Cj1sR4dokfsdhlTKXg1t5Kgejd0").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip() # এরর ফিক্স করা হয়েছে
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100")) # Render এ আপনার অরিজিনাল চ্যানেল আইডি দিবেন

# Pyrogram Client Setup
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, session_string=SESSION_STRING, in_memory=True)

# Upload Folder Setup (Render এর পারমিশন এরর এড়াতে)
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Database Setup (SQLite)
def init_db():
    conn = sqlite3.connect('cloud.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, file_size INTEGER, message_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

@app.on_event("startup")
async def startup():
    await bot.start()

@app.on_event("shutdown")
async def shutdown():
    await bot.stop()

# Frontend Serve করা
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r") as f:
        return f.read()

# File Upload Route
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # 1. ফাইল সার্ভারে টেম্পোরারি সেভ করা
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        file_size = len(content)

    # 2. টেলিগ্রামে পাঠানো (2GB পর্যন্ত সাপোর্ট)
    sent_message = await bot.send_document(chat_id=CHANNEL_ID, document=file_path)
    
    # 3. Database এ সেভ করা
    conn = sqlite3.connect('cloud.db')
    c = conn.cursor()
    c.execute("INSERT INTO files (file_name, file_size, message_id) VALUES (?, ?, ?)", 
              (file.filename, file_size, sent_message.id))
    conn.commit()
    conn.close()

    # 4. টেম্পোরারি ফাইল ডিলিট
    if os.path.exists(file_path):
        os.remove(file_path)

    return {"status": "success", "file_name": file.filename, "message_id": sent_message.id}

# Fetch My Files
@app.get("/files/")
async def get_files():
    conn = sqlite3.connect('cloud.db')
    c = conn.cursor()
    c.execute("SELECT file_name, file_size, message_id FROM files ORDER BY id DESC")
    files = [{"file_name": row[0], "file_size": row[1], "message_id": row[2]} for row in c.fetchall()]
    conn.close()
    return files

# Download File using Streaming
@app.get("/download/{message_id}")
async def download_file(message_id: int):
    message = await bot.get_messages(CHANNEL_ID, message_id)
    
    async def stream_generator():
        async for chunk in bot.stream_media(message):
            yield chunk

    headers = {"Content-Disposition": f"attachment; filename={message.document.file_name}"}
    return StreamingResponse(stream_generator(), headers=headers)

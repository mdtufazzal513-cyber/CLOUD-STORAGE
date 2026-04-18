from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pyrogram import Client
import sqlite3
import os

app = FastAPI()

# Render-এর Environment Variable
API_ID = int(os.getenv("API_ID", "33445387"))
API_HASH = os.getenv("API_HASH", "5b1badf6d0f44c940a2263cef28d6689").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781052287:AAEYTaE5Cj1sR4dokfsdhlTKXg1t5Kgejd0").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "BQH-VgsAZC_puXAZ6e5eDzWyH0COcjwPDqkkQ77m-U3KiD5FbuYXhVfXOa7LUS-dG29vF_QmY6RIzvNyquYX0R225jb5KvUlPH37XyXZwFbzykZFwvlsW8vfBWe3lnRe1Y-CzpSdC1oHxMNfAQmDIXhizTGqyI79RTOlOnnvD0rKFzOZXbK8OmG4yMz967dQfNEM9Tqb2kq2uhDt6qntPeeZRMslvFTz_QLKOLyFSNUE2xkHlYLQnVIjK_Y9XN3J4DZXCxwxOd34COQ5WZsQvuxu3u1ZXZ-n1CxOZA2UKReJDjgArx48RTkxKtkdRpr71DKUZRoWNpT0HiexVj4XMt0RP3Z_qgAAAAILZDl_AQ").strip()
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003984468691")) # আপনার অরিজিনাল চ্যানেল আইডি দিন

# Pyrogram Client Setup
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, session_string=SESSION_STRING)

# Upload Folder Setup
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Database Setup
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

# --- ওয়েবসাইটের ডিজাইন (HTML) সরাসরি কোডে ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Cloud - Telegram Storage</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; min-height: 100vh; }
        .glass { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .hidden { display: none; }
    </style>
</head>
<body class="p-6">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-8 glass p-4 rounded-xl shadow-lg">
            <h1 class="text-2xl font-bold text-blue-400"><i class="fa-solid fa-cloud"></i> MyCloud</h1>
            <div class="space-x-4">
                <button onclick="showTab('upload')" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg transition">Upload</button>
                <button onclick="showTab('files')" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition">My Files</button>
            </div>
        </div>

        <div id="uploadTab" class="glass p-10 rounded-2xl text-center shadow-2xl">
            <h2 class="text-3xl font-semibold mb-6">Upload Files to Cloud</h2>
            <div class="border-2 border-dashed border-gray-500 p-12 rounded-xl mb-6 hover:border-blue-400 transition cursor-pointer" onclick="document.getElementById('fileInput').click()">
                <i class="fa-solid fa-file-arrow-up text-6xl text-gray-400 mb-4"></i>
                <p class="text-gray-300 mb-4">Click here to browse and select file</p>
                <input type="file" id="fileInput" class="hidden">
                <button class="px-6 py-3 bg-blue-600 rounded-lg font-semibold hover:bg-blue-500 transition">Browse File</button>
            </div>
            
            <div id="statusArea" class="hidden">
                <p id="statusText" class="text-yellow-400 font-semibold mb-2">Uploading to Telegram... Please wait.</p>
                <div class="w-full bg-gray-700 rounded-full h-2.5">
                    <div id="progressBar" class="bg-blue-600 h-2.5 rounded-full" style="width: 50%"></div>
                </div>
            </div>
        </div>

        <div id="filesTab" class="hidden glass p-8 rounded-2xl shadow-2xl">
            <h2 class="text-2xl font-semibold mb-6 border-b border-gray-600 pb-2">My Uploaded Files</h2>
            <div id="fileList" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            </div>
        </div>
    </div>

    <script>
        function showTab(tab) {
            document.getElementById('uploadTab').classList.add('hidden');
            document.getElementById('filesTab').classList.add('hidden');
            document.getElementById(tab + 'Tab').classList.remove('hidden');
            if(tab === 'files') loadFiles();
        }

        document.getElementById('fileInput').addEventListener('change', async function() {
            let file = this.files[0];
            if (!file) return;

            document.getElementById('statusArea').classList.remove('hidden');
            document.getElementById('statusText').innerText = `Uploading: ${file.name}...`;
            document.getElementById('progressBar').style.width = '50%';
            document.getElementById('statusText').className = "text-yellow-400 font-semibold mb-2";

            let formData = new FormData();
            formData.append("file", file);

            try {
                let response = await fetch('/upload/', { method: 'POST', body: formData });
                let result = await response.json();

                if (response.ok) {
                    document.getElementById('progressBar').style.width = '100%';
                    document.getElementById('statusText').innerText = "Upload Successful!";
                    document.getElementById('statusText').className = "text-green-400 font-semibold mb-2";
                    setTimeout(() => { 
                        document.getElementById('statusArea').classList.add('hidden'); 
                        document.getElementById('fileInput').value = "";
                    }, 3000);
                } else {
                    throw new Error("Upload Failed");
                }
            } catch (error) {
                document.getElementById('statusText').innerText = "Error uploading file!";
                document.getElementById('statusText').className = "text-red-400 font-semibold mb-2";
            }
        });

        async function loadFiles() {
            let fileList = document.getElementById('fileList');
            fileList.innerHTML = '<p class="text-gray-400">Loading your files...</p>';
            
            try {
                let response = await fetch('/files/');
                let files = await response.json();
                fileList.innerHTML = '';

                if(files.length === 0) {
                    fileList.innerHTML = '<p class="text-gray-400">No files uploaded yet.</p>';
                    return;
                }

                files.forEach(f => {
                    let sizeMB = (f.file_size / (1024 * 1024)).toFixed(2);
                    fileList.innerHTML += `
                        <div class="bg-gray-800 p-4 rounded-lg flex justify-between items-center border border-gray-700 hover:border-blue-500 transition">
                            <div class="overflow-hidden">
                                <p class="font-semibold truncate w-48" title="${f.file_name}">${f.file_name}</p>
                                <p class="text-sm text-gray-400">${sizeMB} MB</p>
                            </div>
                            <a href="/download/${f.message_id}" class="bg-green-600 p-2 rounded-lg hover:bg-green-500 transition" title="Download">
                                <i class="fa-solid fa-download"></i>
                            </a>
                        </div>
                    `;
                });
            } catch(e) {
                fileList.innerHTML = '<p class="text-red-400">Failed to load files.</p>';
            }
        }
    </script>
</body>
</html>
"""

# হোমপেজ রিকোয়েস্ট (এখন কোনো ফোল্ডার খুঁজবে না)
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_PAGE

# ফাইল আপলোডের রিকোয়েস্ট
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        file_size = len(content)

    sent_message = await bot.send_document(chat_id=CHANNEL_ID, document=file_path)
    
    conn = sqlite3.connect('cloud.db')
    c = conn.cursor()
    c.execute("INSERT INTO files (file_name, file_size, message_id) VALUES (?, ?, ?)", 
              (file.filename, file_size, sent_message.id))
    conn.commit()
    conn.close()

    if os.path.exists(file_path):
        os.remove(file_path)

    return {"status": "success", "file_name": file.filename, "message_id": sent_message.id}

# ফাইলের লিস্ট রিকোয়েস্ট
@app.get("/files/")
async def get_files():
    conn = sqlite3.connect('cloud.db')
    c = conn.cursor()
    c.execute("SELECT file_name, file_size, message_id FROM files ORDER BY id DESC")
    files = [{"file_name": row[0], "file_size": row[1], "message_id": row[2]} for row in c.fetchall()]
    conn.close()
    return files

# ফাইল ডাউনলোড রিকোয়েস্ট
@app.get("/download/{message_id}")
async def download_file(message_id: int):
    message = await bot.get_messages(CHANNEL_ID, message_id)
    
    async def stream_generator():
        async for chunk in bot.stream_media(message):
            yield chunk

    headers = {"Content-Disposition": f"attachment; filename={message.document.file_name}"}
    return StreamingResponse(stream_generator(), headers=headers)

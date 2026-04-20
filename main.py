from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pyrogram import Client
import os
import traceback
import re

app = FastAPI()

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

# --- ওয়েবসাইট ডিজাইন ও ফায়ারবেস ইন্টিগ্রেশন (HTML/JS) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Cloud - Secured Storage</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    
    <!-- Firebase SDK (Compat version for simple HTML integration) -->
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-database-compat.js"></script>

    <style>
        body { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; min-height: 100vh; font-family: sans-serif;}
        .glass { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .hidden { display: none !important; }
    </style>
</head>
<body class="p-6">

    <!-- Auth Section (Login/Register) -->
    <div id="authSection" class="max-w-md mx-auto glass p-8 rounded-2xl mt-20 shadow-2xl text-center">
        <h2 class="text-3xl font-bold mb-6 text-blue-400"><i class="fa-solid fa-lock"></i> Login to MyCloud</h2>
        <input type="email" id="email" placeholder="Email" class="w-full mb-4 p-3 rounded bg-gray-800 border border-gray-600 focus:outline-none focus:border-blue-400">
        <input type="password" id="password" placeholder="Password" class="w-full mb-6 p-3 rounded bg-gray-800 border border-gray-600 focus:outline-none focus:border-blue-400">
        <div class="flex space-x-4">
            <button onclick="login()" class="w-full bg-blue-600 p-3 rounded-lg hover:bg-blue-500 transition font-bold">Login</button>
            <button onclick="register()" class="w-full bg-green-600 p-3 rounded-lg hover:bg-green-500 transition font-bold">Register</button>
        </div>
        <p id="authError" class="text-red-400 mt-4 text-sm"></p>
    </div>

    <!-- Main App Section (Hidden until logged in) -->
    <div id="appSection" class="max-w-4xl mx-auto hidden">
        <div class="flex justify-between items-center mb-8 glass p-4 rounded-xl shadow-lg">
            <h1 class="text-2xl font-bold text-blue-400"><i class="fa-solid fa-cloud"></i> MyCloud</h1>
            <div class="space-x-4 flex items-center">
                <span id="userEmailDisplay" class="text-gray-300 text-sm hidden md:inline"></span>
                <button onclick="showTab('upload')" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg transition text-sm">Upload</button>
                <button onclick="showTab('files')" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition text-sm">My Files</button>
                <button onclick="logout()" class="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg transition text-sm"><i class="fa-solid fa-right-from-bracket"></i></button>
            </div>
        </div>

        <div id="uploadTab" class="glass p-10 rounded-2xl text-center shadow-2xl">
            <h2 class="text-3xl font-semibold mb-6">Upload Files to Cloud</h2>
            <div class="border-2 border-dashed border-gray-500 p-12 rounded-xl mb-6 hover:border-blue-400 transition cursor-pointer" onclick="document.getElementById('fileInput').click()">
                <i class="fa-solid fa-file-arrow-up text-6xl text-gray-400 mb-4"></i>
                <p class="text-gray-300 mb-4">Click here to browse and select file</p>
                <input type="file" id="fileInput" class="hidden">
            </div>
            
            <div id="statusArea" class="hidden">
                <p id="statusText" class="text-yellow-400 font-semibold mb-2">Preparing...</p>
                <div class="w-full bg-gray-700 rounded-full h-3 mb-2 border border-gray-600">
                    <div id="progressBar" class="bg-blue-500 h-3 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
                <p id="sizeText" class="text-sm text-gray-400">0 MB of 0 MB</p>
            </div>
        </div>

        <div id="filesTab" class="hidden glass p-8 rounded-2xl shadow-2xl">
            <h2 class="text-2xl font-semibold mb-6 border-b border-gray-600 pb-2">My Uploaded Files</h2>
            <div id="fileList" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
        </div>
    </div>

    <script>
        // 1. Firebase Configuration
        const firebaseConfig = {
            apiKey: "AIzaSyCjv-rmlT00GgTpA0UQ2NnXIyOjXn6ss_s",
            authDomain: "file-to-stream.firebaseapp.com",
            databaseURL: "https://file-to-stream-default-rtdb.asia-southeast1.firebasedatabase.app",
            projectId: "file-to-stream",
            storageBucket: "file-to-stream.firebasestorage.app",
            messagingSenderId: "529016978874",
            appId: "1:529016978874:web:13ae6ef1cd9fa97d76f183",
            measurementId: "G-LG4JV2K9JP"
        };
        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();
        const db = firebase.database();
        let currentUser = null;

        // 2. Auth State Listener
        auth.onAuthStateChanged((user) => {
            if (user) {
                currentUser = user;
                document.getElementById('authSection').classList.add('hidden');
                document.getElementById('appSection').classList.remove('hidden');
                document.getElementById('userEmailDisplay').innerText = user.email;
                loadFilesRealtime();
            } else {
                currentUser = null;
                document.getElementById('authSection').classList.remove('hidden');
                document.getElementById('appSection').classList.add('hidden');
            }
        });

        // 3. Auth Functions
        function register() {
            let email = document.getElementById('email').value;
            let pass = document.getElementById('password').value;
            auth.createUserWithEmailAndPassword(email, pass).catch(err => {
                document.getElementById('authError').innerText = err.message;
            });
        }
        function login() {
            let email = document.getElementById('email').value;
            let pass = document.getElementById('password').value;
            auth.signInWithEmailAndPassword(email, pass).catch(err => {
                document.getElementById('authError').innerText = err.message;
            });
        }
        function logout() { auth.signOut(); }

        // 4. UI Navigation
        function showTab(tab) {
            document.getElementById('uploadTab').classList.add('hidden');
            document.getElementById('filesTab').classList.add('hidden');
            document.getElementById(tab + 'Tab').classList.remove('hidden');
        }

        // 5. Upload with REAL Progress (XHR instead of Fetch)
        document.getElementById('fileInput').addEventListener('change', function() {
            let file = this.files[0];
            if (!file) return;

            document.getElementById('statusArea').classList.remove('hidden');
            document.getElementById('statusText').innerText = `Uploading: ${file.name}`;
            document.getElementById('statusText').className = "text-yellow-400 font-semibold mb-2";
            
            let formData = new FormData();
            formData.append("file", file);

            let xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload/", true);

            // Upload Progress Event
            xhr.upload.onprogress = function(event) {
                if (event.lengthComputable) {
                    let percentComplete = Math.round((event.loaded / event.total) * 100);
                    let loadedMB = (event.loaded / (1024 * 1024)).toFixed(2);
                    let totalMB = (event.total / (1024 * 1024)).toFixed(2);
                    
                    document.getElementById('progressBar').style.width = percentComplete + '%';
                    document.getElementById('statusText').innerText = `Uploading to Server... ${percentComplete}%`;
                    document.getElementById('sizeText').innerText = `${loadedMB} MB of ${totalMB} MB`;
                    
                    if (percentComplete === 100) {
                        document.getElementById('statusText').innerText = "Processing on Telegram (Please wait)...";
                    }
                }
            };

            // Request Finished Event
            xhr.onload = function() {
                if (xhr.status === 200) {
                    let result = JSON.parse(xhr.responseText);
                    if (result.status === "success") {
                        document.getElementById('statusText').innerText = "Upload Complete!";
                        document.getElementById('statusText').className = "text-green-400 font-semibold mb-2";
                        
                        // Save to Firebase Database under this User's UID
                        db.ref('users/' + currentUser.uid + '/files').push({
                            file_name: result.file_name,
                            file_size: result.file_size,
                            message_id: result.message_id,
                            timestamp: firebase.database.ServerValue.TIMESTAMP
                        });

                        setTimeout(() => { 
                            document.getElementById('statusArea').classList.add('hidden'); 
                            document.getElementById('fileInput').value = "";
                            showTab('files');
                        }, 2000);
                    }
                } else {
                    document.getElementById('statusText').innerText = "ERROR Uploading!";
                    document.getElementById('statusText').className = "text-red-400 font-semibold mb-2";
                }
            };

            xhr.send(formData);
        });

        // 6. Realtime Database Fetch & Render
        function loadFilesRealtime() {
            let fileList = document.getElementById('fileList');
            db.ref('users/' + currentUser.uid + '/files').on('value', (snapshot) => {
                fileList.innerHTML = '';
                if (!snapshot.exists()) {
                    fileList.innerHTML = '<p class="text-gray-400">No files uploaded yet.</p>';
                    return;
                }
                
                // Get data and sort by newest first
                let data = [];
                snapshot.forEach(child => { data.push({key: child.key, ...child.val()}); });
                data.sort((a, b) => b.timestamp - a.timestamp);

                data.forEach(f => {
                    let sizeMB = (f.file_size / (1024 * 1024)).toFixed(2);
                    fileList.innerHTML += `
                        <div class="bg-gray-800 p-4 rounded-lg flex justify-between items-center border border-gray-700 hover:border-blue-500 transition">
                            <div class="flex items-center overflow-hidden">
                                <i class="fa-solid fa-file text-2xl text-blue-400 mr-3"></i>
                                <div>
                                    <p class="font-semibold truncate w-40 md:w-48 text-sm" title="${f.file_name}">${f.file_name}</p>
                                    <p class="text-xs text-gray-400">${sizeMB} MB</p>
                                </div>
                            </div>
                            <div class="flex space-x-2">
                                <a href="/download/${f.message_id}" target="_blank" class="bg-green-600 p-2 rounded-lg hover:bg-green-500 transition text-white" title="Download">
                                    <i class="fa-solid fa-download"></i>
                                </a>
                                <button onclick="deleteFile('${f.key}', ${f.message_id})" class="bg-red-600 p-2 rounded-lg hover:bg-red-500 transition text-white" title="Delete">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
            });
        }

        // 7. Delete Logic (Backend Telegram + Firebase DB)
        async function deleteFile(dbKey, messageId) {
            if(!confirm("Are you sure you want to delete this file?")) return;
            try {
                // Remove from Telegram (via Python API)
                await fetch(`/delete/${messageId}`, { method: 'DELETE' });
                // Remove from Firebase Realtime DB
                db.ref(`users/${currentUser.uid}/files/${dbKey}`).remove();
            } catch(e) {
                alert("Error deleting file.");
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_PAGE

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
        # ওয়েবসাইট (JS) এই ডাটা নিয়ে Firebase-এ সেভ করবে।
        return {"status": "success", "file_name": file.filename, "file_size": file_size, "message_id": sent_message.id}

    except Exception as e:
        print(f"!!! UPLOAD ERROR: {e} !!!")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})


# --- নতুন: Resumable Download System (Pause/Resume Support) ---
@app.get("/download/{message_id}")
async def download_file(message_id: int, request: Request):
    try:
        message = await bot.get_messages(CHANNEL_ID, message_id)
        if not message or not getattr(message, "document", None) and not getattr(message, "video", None) and not getattr(message, "photo", None):
            return JSONResponse(status_code=404, content={"error": "File not found"})

        media = message.document or message.video or message.photo
        file_name = getattr(media, "file_name", f"file_{message_id}")
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "application/octet-stream")

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
                status_code = 206 # 206 Partial Content (IDM বা ব্রাউজার বুঝবে যে ফাইল কাটা যায়)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f'attachment; filename="{file_name}"'
        }

        # Pyrogram থেকে নির্দিষ্ট বাইট (offset) থেকে স্ট্রিম করা
        async def ranged_file_streamer():
            async for chunk in bot.stream_media(message, offset=start, limit=(end - start + 1)):
                yield chunk

        return StreamingResponse(ranged_file_streamer(), status_code=status_code, headers=headers, media_type=mime_type)

    except Exception as e:
        print(f"Download Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

@app.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    try:
        await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=message_id)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

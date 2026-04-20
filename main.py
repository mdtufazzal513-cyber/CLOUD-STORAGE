from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client
import os
import re

app = FastAPI()

# অ্যাডমিন প্যানেল যেন এই সার্ভারকে এক্সেস করতে পারে তাই CORS এলাউ করা হলো
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment Variables
API_ID = int(os.getenv("API_ID", "33445387"))
API_HASH = os.getenv("API_HASH", "5b1badf6d0f44c940a2263cef28d6689").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "BQH-VgsAjXAtpA7_8WzYjaImZMmoFJUd6RFEut4X32b15iWR-62IjLNTLZQt1xYigp13Sm6rcUVvXEuUdpoJDhwkaSTOCcT2CWGtRPslhvdY7JueDWhne_rJtCSqoV0AcADg21xCGuDNjLl4LaIry4VQerxgYEOmD93djo0MPUZRxoHuEAcNxTrCxr_IqC6fzEsMxB5Mqk1nnNM_-ZBsNKSzfvCiCljgVktNXXilhmchvLTFXs2EvYSHewxyJRuTK-NAVupaUKywQE1hVNWKMmJNKdIbXdPzGFbITV4wdY54ezBTsd1pP-NfLGb_VJYUkaQmeEy5EP49-Ak8gSkZL4AbrMqFKAAAAAIE58I1AA").strip()
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003984468691"))

bot = Client("my_backend", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
async def startup():
    print("--- Starting Server & Connecting to Telegram ---")
    await bot.start()

@app.on_event("shutdown")
async def shutdown():
    await bot.stop()

# ==========================================
# এখানেই ইউজার প্যানেলের HTML কোড থাকবে
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyCloud - Premium Storage</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-database-compat.js"></script>
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; padding-bottom: 80px;}
        .card { background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; }
        .hidden { display: none !important; }
        .circle-wrap { width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: conic-gradient(#3b82f6 0%, #334155 0%); }
        .inner-circle { width: 64px; height: 64px; background-color: #1e293b; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background-color: #1e293b; border-top: 1px solid #334155; display: flex; justify-content: space-around; padding: 10px 0; z-index: 50;}
        .upload-btn { background: #3b82f6; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transform: translateY(-30px); border: 4px solid #0f172a; box-shadow: 0 4px 10px rgba(0,0,0,0.5); transition: 0.2s;}
        .upload-btn:active { transform: translateY(-25px); }
        .nav-btn { color: #64748b; transition: 0.3s; display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 12px;}
        .nav-btn.active { color: #3b82f6; }
    </style>
</head>
<body>

    <div id="authSection" class="p-6 max-w-sm mx-auto mt-20 text-center">
        <div class="mb-8">
            <i class="fa-solid fa-cloud text-6xl text-blue-500 mb-4"></i>
            <h2 class="text-3xl font-bold text-white">MyCloud</h2>
        </div>
        <input type="email" id="email" placeholder="Email Address" class="w-full mb-4 p-3 rounded bg-slate-800 border border-slate-700 outline-none focus:border-blue-500">
        <input type="password" id="password" placeholder="Password" class="w-full mb-6 p-3 rounded bg-slate-800 border border-slate-700 outline-none focus:border-blue-500">
        <button onclick="login()" class="w-full bg-blue-600 p-3 rounded-lg mb-4 font-bold hover:bg-blue-500">Sign In</button>
        <button onclick="register()" class="w-full bg-slate-700 p-3 rounded-lg font-bold hover:bg-slate-600">Create Account</button>
        <p id="authError" class="text-red-400 mt-4 text-sm"></p>
    </div>

    <div id="appSection" class="hidden">
        <div class="flex justify-between items-center p-6">
            <div class="flex items-center space-x-3">
                <div class="bg-blue-500 p-3 rounded-full shadow-lg"><i class="fa-solid fa-user text-white"></i></div>
                <div>
                    <h3 class="font-bold text-lg leading-tight">Welcome Back</h3>
                    <p id="userEmail" class="text-xs text-slate-400">guest</p>
                </div>
            </div>
            <div class="bg-slate-800 p-2 rounded-full border border-yellow-500/30 shadow-[0_0_15px_rgba(234,179,8,0.2)]">
                <i class="fa-solid fa-crown text-yellow-400 text-xl px-1"></i>
            </div>
        </div>

        <div id="homeTab">
            <div class="px-6 mb-6">
                <div class="card p-5 flex justify-between items-center shadow-lg relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-32 h-32 bg-blue-500 opacity-5 rounded-full blur-3xl"></div>
                    <div class="z-10">
                        <h3 class="text-lg font-bold mb-1">Storage Overview</h3>
                        <div class="flex items-center gap-2 mb-2">
                            <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
                            <p class="text-sm font-semibold text-blue-400" id="storageText">0.00 MB <span class="text-slate-400 font-normal">| Total: 25.00 GB</span></p>
                        </div>
                        <p class="text-xs font-semibold text-yellow-500 bg-yellow-500/10 inline-block px-2 py-1 rounded-full"><i class="fa-solid fa-gem mr-1"></i> Premium Active</p>
                    </div>
                    <div class="circle-wrap z-10" id="progressCircle">
                        <div class="inner-circle text-sm font-bold text-white" id="storagePercent">0%</div>
                    </div>
                </div>
            </div>

            <div class="px-6 mb-8">
                <div class="grid grid-cols-2 gap-4">
                    <div class="card p-4 hover:border-orange-500 transition cursor-pointer" onclick="switchTab('filesTab')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="bg-orange-500/20 p-3 rounded-lg"><i class="fa-solid fa-image text-orange-400 text-xl"></i></div>
                            <span class="text-xs text-slate-400 font-semibold" id="imgCatSize">0.00 MB</span>
                        </div>
                        <h4 class="font-bold">Images</h4>
                    </div>
                    <div class="card p-4 hover:border-cyan-500 transition cursor-pointer" onclick="switchTab('filesTab')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="bg-cyan-500/20 p-3 rounded-lg"><i class="fa-solid fa-circle-play text-cyan-400 text-xl"></i></div>
                            <span class="text-xs text-slate-400 font-semibold" id="vidCatSize">0.00 MB</span>
                        </div>
                        <h4 class="font-bold">Videos</h4>
                    </div>
                    <div class="card p-4 hover:border-green-500 transition cursor-pointer" onclick="switchTab('filesTab')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="bg-green-500/20 p-3 rounded-lg"><i class="fa-solid fa-file-lines text-green-400 text-xl"></i></div>
                            <span class="text-xs text-slate-400 font-semibold" id="docCatSize">0.00 MB</span>
                        </div>
                        <h4 class="font-bold">Documents</h4>
                    </div>
                    <div class="card p-4 hover:border-purple-500 transition cursor-pointer" onclick="switchTab('filesTab')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="bg-purple-500/20 p-3 rounded-lg"><i class="fa-solid fa-music text-purple-400 text-xl"></i></div>
                            <span class="text-xs text-slate-400 font-semibold" id="audCatSize">0.00 MB</span>
                        </div>
                        <h4 class="font-bold">Audio</h4>
                    </div>
                </div>
            </div>
            
            <div class="px-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="font-bold text-lg">Recent Files</h3>
                    <button onclick="switchTab('filesTab')" class="text-sm text-blue-400 hover:text-blue-300">See All</button>
                </div>
                <div id="recentFileList" class="space-y-3"></div>
            </div>
        </div>

        <div id="filesTab" class="hidden px-6">
            <div class="flex justify-between items-center mb-6 mt-2 border-b border-slate-700 pb-4">
                <h3 class="font-bold text-xl"><i class="fa-solid fa-folder-open text-blue-500 mr-2"></i> All Files</h3>
            </div>
            <div id="fullFileList" class="space-y-3"></div>
        </div>

        <div class="bottom-nav">
            <button class="nav-btn active" id="btnHome" onclick="switchTab('homeTab')"><i class="fa-solid fa-house text-xl mb-1"></i></button>
            <button class="nav-btn" id="btnFiles" onclick="switchTab('filesTab')"><i class="fa-solid fa-file-lines text-xl mb-1"></i></button>
            <button onclick="document.getElementById('fileInput').click()" class="upload-btn text-white"><i class="fa-solid fa-plus text-2xl"></i></button>
            <button class="nav-btn" onclick="alert('Favorites coming soon!')"><i class="fa-solid fa-heart text-xl mb-1"></i></button>
            <button class="nav-btn text-red-400 hover:text-red-300" onclick="logout()"><i class="fa-solid fa-right-from-bracket text-xl mb-1"></i></button>
        </div>

        <div id="uploadModal" class="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center hidden z-50 px-4 backdrop-blur-sm">
            <div class="card p-8 w-full max-w-sm text-center shadow-2xl border border-blue-500/30">
                <i class="fa-solid fa-cloud-arrow-up text-5xl text-blue-500 mb-4 animate-bounce"></i>
                <h3 class="font-bold text-lg mb-2" id="uploadStatus">Preparing...</h3>
                <div class="w-full bg-slate-700 h-3 rounded-full mb-3 overflow-hidden">
                    <div id="uploadProgress" class="bg-gradient-to-r from-blue-600 to-blue-400 h-full rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
                <p id="uploadDetails" class="text-sm text-slate-400 font-mono">0.00 MB / 0.00 MB</p>
                <p id="serverWakeUpMsg" class="text-xs text-yellow-500 mt-3 hidden"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Checking connection...</p>
            </div>
        </div>

        <input type="file" id="fileInput" class="hidden">
    </div>

    <script>
        const firebaseConfig = {
            apiKey: "AIzaSyCjv-rmlT00GgTpA0UQ2NnXIyOjXn6ss_s",
            authDomain: "file-to-stream.firebaseapp.com",
            databaseURL: "https://file-to-stream-default-rtdb.asia-southeast1.firebasedatabase.app",
            projectId: "file-to-stream",
            storageBucket: "file-to-stream.firebasestorage.app",
            messagingSenderId: "529016978874",
            appId: "1:529016978874:web:13ae6ef1cd9fa97d76f183"
        };
        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();
        const db = firebase.database();
        let currentUser = null;

        function switchTab(tabId) {
            document.getElementById('homeTab').classList.add('hidden');
            document.getElementById('filesTab').classList.add('hidden');
            document.getElementById(tabId).classList.remove('hidden');
            document.getElementById('btnHome').classList.remove('active');
            document.getElementById('btnFiles').classList.remove('active');
            if(tabId === 'homeTab') document.getElementById('btnHome').classList.add('active');
            if(tabId === 'filesTab') document.getElementById('btnFiles').classList.add('active');
        }

        auth.onAuthStateChanged(user => {
            if (user) {
                currentUser = user;
                document.getElementById('authSection').classList.add('hidden');
                document.getElementById('appSection').classList.remove('hidden');
                document.getElementById('userEmail').innerText = user.email;
                loadFiles();
            } else {
                document.getElementById('authSection').classList.remove('hidden');
                document.getElementById('appSection').classList.add('hidden');
            }
        });

        function register() {
            auth.createUserWithEmailAndPassword(document.getElementById('email').value, document.getElementById('password').value)
                .catch(err => document.getElementById('authError').innerText = err.message);
        }
        function login() {
            auth.signInWithEmailAndPassword(document.getElementById('email').value, document.getElementById('password').value)
                .catch(err => document.getElementById('authError').innerText = err.message);
        }
        function logout() { auth.signOut(); }

        document.getElementById('fileInput').addEventListener('change', function() {
            let file = this.files[0];
            if (!file) return;

            document.getElementById('uploadModal').classList.remove('hidden');
            document.getElementById('uploadStatus').innerText = "Connecting...";
            document.getElementById('uploadProgress').style.width = '0%';
            document.getElementById('uploadDetails').innerText = `0.00 MB / ${(file.size/1048576).toFixed(2)} MB`;
            document.getElementById('serverWakeUpMsg').classList.remove('hidden'); 

            let formData = new FormData();
            formData.append("file", file);

            let xhr = new XMLHttpRequest();
            // একই সার্ভার তাই সরাসরি /upload/ কল করা হলো
            xhr.open("POST", "/upload/", true);

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    document.getElementById('serverWakeUpMsg').classList.add('hidden');
                    document.getElementById('uploadStatus').innerText = "Uploading...";
                    let p = Math.round((e.loaded / e.total) * 100);
                    document.getElementById('uploadProgress').style.width = p + '%';
                    document.getElementById('uploadDetails').innerText = `${(e.loaded/1048576).toFixed(2)} MB / ${(e.total/1048576).toFixed(2)} MB`;
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    let res = JSON.parse(xhr.responseText);
                    if(res.status === "success") {
                        db.ref(`users/${currentUser.uid}/files`).push({
                            name: res.file_name, size: res.file_size, message_id: res.message_id, time: Date.now()
                        });
                        document.getElementById('uploadStatus').innerText = "Upload Complete!";
                    } else {
                        document.getElementById('uploadStatus').innerText = "Failed: " + res.message;
                    }
                } else {
                    document.getElementById('uploadStatus').innerText = "Server Error!";
                }
                setTimeout(() => document.getElementById('uploadModal').classList.add('hidden'), 2000);
                document.getElementById('fileInput').value = "";
            };
            xhr.onerror = function() {
                document.getElementById('uploadStatus').innerText = "Network Error!";
                setTimeout(() => document.getElementById('uploadModal').classList.add('hidden'), 2000);
                document.getElementById('fileInput').value = "";
            };
            xhr.send(formData);
        });

        function loadFiles() {
            db.ref(`users/${currentUser.uid}/files`).on('value', snap => {
                let allFilesHtml = "";
                let recentFilesHtml = "";
                let totalBytes = 0;
                let data =[];
                let categories = { img: 0, vid: 0, doc: 0, aud: 0 };

                snap.forEach(c => { 
                    let val = c.val();
                    let safeSize = val.size || val.file_size || 0;
                    totalBytes += safeSize;
                    data.push({key: c.key, ...val, size: safeSize}); 
                });
                data.sort((a,b) => (b.time || 0) - (a.time || 0));

                data.forEach((f, index) => {
                    let safeName = f.name || f.file_name || "Unknown_File";
                    let safeTime = f.time || Date.now();
                    let msgId = f.message_id; 
                    let mb = (f.size / 1048576).toFixed(2);

                    let isImage = safeName.match(/\.(jpg|jpeg|png|gif|webp)$/i);
                    let isVideo = safeName.match(/\.(mp4|mkv|avi|mov)$/i);
                    let isAudio = safeName.match(/\.(mp3|wav|ogg|m4a)$/i);
                    
                    let iconColor = isImage ? "text-orange-400" : (isVideo ? "text-cyan-400" : (isAudio ? "text-purple-400" : "text-green-400"));
                    let bgIcon = isImage ? "bg-orange-500/20" : (isVideo ? "bg-cyan-500/20" : (isAudio ? "bg-purple-500/20" : "bg-green-500/20"));
                    let iconType = isImage ? "fa-image" : (isVideo ? "fa-circle-play" : (isAudio ? "fa-music" : "fa-file-lines"));

                    if(isImage) categories.img += f.size;
                    else if(isVideo) categories.vid += f.size;
                    else if(isAudio) categories.aud += f.size;
                    else categories.doc += f.size;

                    // একই সার্ভার হওয়ায় শুধু /download/ ব্যবহার করা হলো
                    let downloadLink = `/download/${msgId}`;

                    let fileCard = `
                        <div class="card p-3 flex justify-between items-center hover:bg-slate-800 transition">
                            <div class="flex items-center overflow-hidden w-[70%]">
                                <div class="${bgIcon} w-12 h-12 rounded-xl flex items-center justify-center mr-3 shrink-0"><i class="fa-solid ${iconType} ${iconColor} text-xl"></i></div>
                                <div class="overflow-hidden">
                                    <p class="font-semibold text-sm truncate w-full text-slate-200">${safeName}</p>
                                    <p class="text-[11px] text-slate-400 mt-0.5">${mb} MB • ${(new Date(safeTime)).toLocaleDateString()}</p>
                                </div>
                            </div>
                            <div class="flex space-x-2">
                                <a href="${downloadLink}" target="_blank" class="bg-green-500/10 text-green-400 p-2.5 rounded-lg hover:bg-green-500/20 transition cursor-pointer"><i class="fa-solid fa-download"></i></a>
                                <button onclick="deleteFile('${f.key}', ${msgId})" class="bg-red-500/10 text-red-400 p-2.5 rounded-lg hover:bg-red-500/20 transition cursor-pointer"><i class="fa-solid fa-trash"></i></button>
                            </div>
                        </div>`;
                    
                    allFilesHtml += fileCard;
                    if(index < 3) recentFilesHtml += fileCard; 
                });

                let emptyMsg = "<div class='text-center py-8 text-slate-500'><i class='fa-solid fa-folder-open text-4xl mb-2'></i><p>No files uploaded yet.</p></div>";
                
                document.getElementById('fullFileList').innerHTML = allFilesHtml || emptyMsg;
                document.getElementById('recentFileList').innerHTML = recentFilesHtml || emptyMsg;

                let totalMB = (totalBytes / 1048576).toFixed(2);
                let percent = ((totalMB / 25600) * 100).toFixed(2); 
                document.getElementById('storageText').innerText = `${totalMB} MB `;
                document.getElementById('storagePercent').innerText = `${percent}%`;
                document.getElementById('progressCircle').style.background = `conic-gradient(#3b82f6 ${percent}%, #334155 0%)`;

                document.getElementById('imgCatSize').innerText = (categories.img / 1048576).toFixed(2) + " MB";
                document.getElementById('vidCatSize').innerText = (categories.vid / 1048576).toFixed(2) + " MB";
                document.getElementById('docCatSize').innerText = (categories.doc / 1048576).toFixed(2) + " MB";
                document.getElementById('audCatSize').innerText = (categories.aud / 1048576).toFixed(2) + " MB";
            });
        }

        async function deleteFile(key, msgId) {
            if(!confirm("Are you sure you want to delete this file permanently?")) return;
            try {
                fetch(`/delete/${msgId}`, {method: 'DELETE'});
                db.ref(`users/${currentUser.uid}/files/${key}`).remove();
            } catch(e) { console.log(e); }
        }
    </script>
</body>
</html>
"""

# ==========================================
# FastAPI Routes (ব্যাকএন্ড API)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    # সরাসরি উপরের HTML ভেরিয়েবলটি রিটার্ন করবে
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

        return {"status": "success", "file_name": file.filename, "file_size": file_size, "message_id": sent_message.id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.get("/download/{message_id}")
async def download_file(message_id: int, request: Request):
    try:
        message = await bot.get_messages(CHANNEL_ID, message_id)
        if not message: return JSONResponse(status_code=404, content={"error": "Not found"})

        media = message.document or message.video or message.photo
        file_name = getattr(media, "file_name", f"file_{message_id}")
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "application/octet-stream")

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

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f'attachment; filename="{file_name}"'
        }

        async def ranged_file_streamer():
            async for chunk in bot.stream_media(message, offset=start, limit=(end - start + 1)):
                yield chunk

        return StreamingResponse(ranged_file_streamer(), status_code=status_code, headers=headers, media_type=mime_type)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/delete/{message_id}")
async def delete_file_endpoint(message_id: int):
    try:
        await bot.delete_messages(chat_id=CHANNEL_ID, message_ids=message_id)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

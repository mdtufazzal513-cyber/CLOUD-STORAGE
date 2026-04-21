from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pyrogram import Client
import os
import traceback
import re
import asyncio

# সার্ভারের ওপর চাপ কমানোর জন্য ট্রাফিক কন্ট্রোলার (Max 1 concurrent download to prevent crashes)
MAX_CONCURRENT_DOWNLOADS = 1
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

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
                    try {
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

# --- ওয়েবসাইট ডিজাইন ও ফায়ারবেস ইন্টিগ্রেশন (HTML/JS) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0f172a">
    <title>MyCloud</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    
    <!-- Firebase SDK -->
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-auth-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.8.0/firebase-database-compat.js"></script>

    <style>
        /* Native App Feel Utilities */
        body { 
            background-color: #0f172a; 
            color: #f8fafc; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            -webkit-tap-highlight-color: transparent; /* Removes web touch highlight */
            user-select: none; /* Prevents text selection like an app */
        }
        /* Allow text selection only inside inputs and specific texts */
        input, .selectable { user-select: text; }
        
        /* App Layout setup */
        .app-container {
            max-width: 500px; /* Mobile width constraint for web viewing */
            margin: 0 auto;
            min-height: 100vh;
            background-color: #1e293b;
            position: relative;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
        }

        .glass-header { 
            background: rgba(30, 41, 59, 0.85); 
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .glass-bottom-nav {
            background: rgba(30, 41, 59, 0.95); 
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: env(safe-area-inset-bottom); /* iPhone X+ notch support */
        }

        .hidden { display: none !important; }
        
        /* Smooth Fade In */
        .fade-in { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* Custom Scrollbar for file list */
        .scrollable-content::-webkit-scrollbar { width: 0px; background: transparent; }
    </style>
</head>
<body class="bg-slate-900">

    <div class="app-container">

        <!-- ================= TOAST NOTIFICATION (Background Process) ================= -->
        <div id="toastNotification" class="fixed top-10 left-1/2 transform -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-full shadow-2xl flex items-center gap-3 z-[100] transition-all duration-300 opacity-0 -translate-y-10 pointer-events-none border border-slate-700">
            <i class="fa-solid fa-circle-notch fa-spin text-blue-400 text-lg"></i>
            <span id="toastMessage" class="text-sm font-semibold tracking-wide">Processing, please wait...</span>
        </div>

        <!-- ================= AUTH SECTION ================= -->
        <div id="authSection" class="flex-1 flex flex-col justify-center items-center p-6 fade-in">
            <div class="w-16 h-16 bg-blue-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg shadow-blue-500/30">
                <i class="fa-solid fa-cloud text-3xl text-white"></i>
            </div>
            <h1 class="text-3xl font-bold mb-2">MyCloud</h1>
            <p class="text-slate-400 mb-8 text-sm">Your secure unlimited storage</p>
            
            <div class="w-full space-y-4">
                <div class="relative">
                    <i class="fa-solid fa-envelope absolute left-4 top-4 text-slate-400"></i>
                    <input type="email" id="email" placeholder="Email Address" class="w-full pl-12 pr-4 py-3 rounded-xl bg-slate-800 border border-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition text-white">
                </div>
                <div class="relative">
                    <i class="fa-solid fa-lock absolute left-4 top-4 text-slate-400"></i>
                    <input type="password" id="password" placeholder="Password" class="w-full pl-12 pr-4 py-3 rounded-xl bg-slate-800 border border-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition text-white">
                </div>
                
                <div class="pt-2 flex flex-col gap-3">
                    <button onclick="login()" class="w-full bg-blue-600 active:bg-blue-700 py-3.5 rounded-xl font-bold text-white shadow-lg shadow-blue-600/30 transition">Sign In</button>
                    <button onclick="register()" class="w-full bg-slate-800 active:bg-slate-700 py-3.5 rounded-xl font-bold text-blue-400 border border-slate-700 transition">Create Account</button>
                </div>
                <p id="authError" class="text-red-400 text-center mt-2 text-sm font-medium"></p>
            </div>
        </div>


        <!-- ================= MAIN APP SECTION ================= -->
        <div id="appSection" class="hidden flex-1 flex flex-col h-screen max-h-screen">
            
            <!-- App Header -->
            <header class="glass-header fixed top-0 w-full max-w-[500px] z-50 px-5 py-4 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center shadow-md">
                        <i class="fa-solid fa-cloud text-sm text-white"></i>
                    </div>
                    <h1 class="text-lg font-bold">MyCloud</h1>
                </div>
                <!-- Mini Profile Avatar -->
                <div class="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center border border-slate-600">
                    <i class="fa-solid fa-user text-xs text-slate-300"></i>
                </div>
            </header>

            <!-- Main Content Area (Scrollable) -->
            <main class="flex-1 overflow-y-auto scrollable-content pt-20 pb-24 px-4">
                
                <!-- 0. HOME TAB (Placeholder) -->
                <div id="homeTab" class="hidden fade-in flex flex-col items-center justify-center h-full pt-10">
                    <div class="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6 shadow-lg border border-slate-700">
                        <i class="fa-solid fa-house text-4xl text-slate-500"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-slate-300">Home Dashboard</h2>
                    <p class="text-slate-500 text-sm mt-2 text-center px-6">Exciting new features are coming soon to this space!</p>
                </div>

                <!-- 1. FILES TAB -->
                <div id="filesTab" class="fade-in">
                    <div class="flex justify-between items-end mb-4 px-1">
                        <h2 class="text-xl font-bold text-white">Recent Files</h2>
                        <span id="fileCountBadge" class="text-xs bg-slate-800 px-2 py-1 rounded-md text-slate-400">0 Items</span>
                    </div>
                    <div id="fileList" class="flex flex-col gap-3">
                        <!-- JS Will Populate This with Native Style Cards -->
                    </div>
                </div>

                <!-- 2. UPLOAD TAB -->
                <div id="uploadTab" class="hidden fade-in flex flex-col items-center justify-center h-full pt-10">
                    <h2 class="text-2xl font-bold mb-2">Upload File</h2>
                    <p class="text-slate-400 text-sm mb-8 text-center px-4">Select any file from your device to upload securely to the cloud.</p>
                    
                    <!-- Native-like Upload Button Area -->
                    <div class="w-full max-w-xs relative group cursor-pointer" onclick="document.getElementById('fileInput').click()">
                        <div class="absolute inset-0 bg-blue-500 rounded-3xl blur opacity-20"></div>
                        <div class="relative bg-slate-800 border-2 border-dashed border-slate-600 rounded-3xl p-10 flex flex-col items-center text-center transition active:bg-slate-700">
                            <div class="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mb-4 text-blue-400">
                                <i class="fa-solid fa-arrow-up-from-bracket text-2xl"></i>
                            </div>
                            <span class="font-semibold text-blue-400">Tap to Browse</span>
                            <span class="text-xs text-slate-500 mt-1">Files, Photos, Videos</span>
                        </div>
                        <!-- multiple অ্যাট্রিবিউট যুক্ত করা হয়েছে -->
                        <input type="file" id="fileInput" class="hidden" multiple>
                    </div>

                    <!-- Dynamic Multiple Upload Progress UI Container -->
                    <div id="uploadListContainer" class="w-full max-w-md mt-6 flex flex-col gap-3 px-2 pb-10">
                        <!-- জাভাস্ক্রিপ্ট এখানে কার্ডগুলো তৈরি করবে -->
                    </div>
                </div>

                <!-- 3. PROFILE TAB -->
                <div id="profileTab" class="hidden fade-in">
                    <h2 class="text-xl font-bold text-white mb-6 px-1">Account</h2>
                    
                    <div class="bg-slate-800 rounded-2xl p-5 border border-slate-700 mb-6 flex items-center gap-4">
                        <div class="w-14 h-14 rounded-full bg-blue-500/20 text-blue-500 flex items-center justify-center text-2xl">
                            <i class="fa-solid fa-user"></i>
                        </div>
                        <div class="overflow-hidden">
                            <p class="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Logged in as</p>
                            <p id="userEmailDisplay" class="font-semibold text-white truncate text-sm selectable">user@email.com</p>
                        </div>
                    </div>

                    <div class="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden">
                        <button onclick="logout()" class="w-full p-4 flex items-center text-red-400 active:bg-slate-700 transition text-left">
                            <div class="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center mr-3">
                                <i class="fa-solid fa-right-from-bracket"></i>
                            </div>
                            <span class="font-semibold text-sm">Log Out</span>
                        </button>
                    </div>
                </div>

            </main>

            <!-- Floating Action Button (Upload) - Moved to bottom-right -->
            <button onclick="showTab('upload')" id="nav-upload" class="fixed bottom-24 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-500 rounded-full flex items-center justify-center text-white shadow-[0_10px_20px_rgba(37,99,235,0.4)] active:scale-90 transition-all duration-200 z-50 border border-blue-400">
                <i class="fa-solid fa-plus text-2xl"></i>
            </button>

            <!-- Bottom Navigation Bar (Native App Style) -->
            <nav class="glass-bottom-nav fixed bottom-0 w-full max-w-[500px] z-50 px-8 py-3 flex justify-between items-center rounded-t-3xl shadow-[0_-10px_30px_rgba(0,0,0,0.3)]">
                
                <!-- Home Button (Left) -->
                <button onclick="showTab('home')" id="nav-home" class="nav-item flex flex-col items-center gap-1 p-2 text-slate-500 w-16 transition-colors duration-200">
                    <i class="fa-solid fa-house text-xl mb-0.5"></i>
                    <span class="text-[10px] font-semibold">Home</span>
                </button>

                <!-- Files Button (Center) -->
                <button onclick="showTab('files')" id="nav-files" class="nav-item flex flex-col items-center gap-1 p-2 text-blue-500 w-16 transition-colors duration-200">
                    <i class="fa-solid fa-folder-open text-xl mb-0.5"></i>
                    <span class="text-[10px] font-semibold">Files</span>
                </button>
                
                <!-- Profile Button (Right) -->
                <button onclick="showTab('profile')" id="nav-profile" class="nav-item flex flex-col items-center gap-1 p-2 text-slate-500 w-16 transition-colors duration-200">
                    <i class="fa-solid fa-user text-xl mb-0.5"></i>
                    <span class="text-[10px] font-semibold">Profile</span>
                </button>
            </nav>

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
                showTab('files'); // Default tab on login
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
            if(!email || !pass) { document.getElementById('authError').innerText = "Enter email and password"; return; }
            auth.createUserWithEmailAndPassword(email, pass).catch(err => {
                document.getElementById('authError').innerText = err.message;
            });
        }
        function login() {
            let email = document.getElementById('email').value;
            let pass = document.getElementById('password').value;
            if(!email || !pass) { document.getElementById('authError').innerText = "Enter email and password"; return; }
            auth.signInWithEmailAndPassword(email, pass).catch(err => {
                document.getElementById('authError').innerText = err.message;
            });
        }
        function logout() { auth.signOut(); }

        // 4. UI Navigation (Bottom Nav Logic)
        function showTab(tab) {
            // Hide all tabs (নতুন Home ট্যাব যুক্ত করা হয়েছে)
            ['home', 'files', 'upload', 'profile'].forEach(id => {
                document.getElementById(id + 'Tab').classList.add('hidden');
            });
            
            // Show selected tab
            document.getElementById(tab + 'Tab').classList.remove('hidden');

            // স্মার্ট লজিক: যখন ইউজার Upload পেজে থাকবে, তখন ফ্লোটিং প্লাস (+) বাটনটি লুকিয়ে যাবে
            let fab = document.getElementById('nav-upload');
            if(tab === 'upload') {
                fab.classList.add('scale-0', 'opacity-0', 'pointer-events-none');
            } else {
                fab.classList.remove('scale-0', 'opacity-0', 'pointer-events-none');
            }

            // Reset Bottom Nav Colors
            document.getElementById('nav-home').className = "nav-item flex flex-col items-center gap-1 p-2 text-slate-500 w-16 transition-colors duration-200";
            document.getElementById('nav-files').className = "nav-item flex flex-col items-center gap-1 p-2 text-slate-500 w-16 transition-colors duration-200";
            document.getElementById('nav-profile').className = "nav-item flex flex-col items-center gap-1 p-2 text-slate-500 w-16 transition-colors duration-200";

            // Set Active Color
            if(tab === 'home') {
                document.getElementById('nav-home').classList.replace('text-slate-500', 'text-blue-500');
            } else if(tab === 'files') {
                document.getElementById('nav-files').classList.replace('text-slate-500', 'text-blue-500');
            } else if(tab === 'profile') {
                document.getElementById('nav-profile').classList.replace('text-slate-500', 'text-blue-500');
            }
            
            // Scroll to top
            document.querySelector('main').scrollTo(0,0);
        }

        // 5. Multi-Upload System with Queue (Sequential) & Cancel Support
        let uploadQueue = [];
        let isUploading = false;

        document.getElementById('fileInput').addEventListener('change', function() {
            let files = this.files;
            if (files.length === 0) return;

            let uploadListContainer = document.getElementById('uploadListContainer');

            Array.from(files).forEach((file, index) => {
                let fileId = 'upload_' + Date.now() + '_' + index;
                
                let uploadCard = document.createElement('div');
                uploadCard.className = "bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-md fade-in relative";
                uploadCard.id = fileId;
                
                uploadCard.innerHTML = `
                    <div class="flex justify-between items-center mb-2">
                        <div class="overflow-hidden pr-2 flex-1">
                            <p class="text-sm font-semibold text-blue-400 truncate">${file.name}</p>
                            <p class="text-xs text-slate-400 size-text mt-0.5">0 MB / ${(file.size / (1024*1024)).toFixed(2)} MB</p>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="text-xs font-bold text-slate-300 percent-text w-8 text-right">0%</span>
                            <button class="w-8 h-8 rounded-full bg-slate-700 text-red-400 hover:bg-red-500 hover:text-white flex items-center justify-center transition cancel-btn" title="Cancel Upload">
                                <i class="fa-solid fa-xmark"></i>
                            </button>
                        </div>
                    </div>
                    <div class="w-full bg-slate-900 rounded-full h-2 mb-2 overflow-hidden border border-slate-700">
                        <div class="bg-slate-600 h-full rounded-full transition-all duration-300 progress-bar" style="width: 0%"></div>
                    </div>
                    <p class="text-[11px] font-semibold text-slate-400 status-text tracking-wide">Waiting in queue...</p>
                `;
                
                uploadListContainer.appendChild(uploadCard);
                
                // আপলোড শুরু না করে লাইনে দাঁড় করানো হলো
                uploadQueue.push({ file: file, card: uploadCard });
            });
            
            this.value = ""; 
            processNextUpload(); // লাইনের প্রথমটিকে শুরু করার জন্য কল
        });

        // লাইনের পরবর্তী ফাইল প্রসেস করার ফাংশন
        function processNextUpload() {
            if (isUploading || uploadQueue.length === 0) return;
            
            let currentItem = uploadQueue.shift(); // লাইনের প্রথম ফাইল বের করা
            isUploading = true;
            startSingleUpload(currentItem.file, currentItem.card);
        }

        // আপলোডের ক্ষেত্রেও async ব্যবহার করতে হবে যাতে সার্ভারের জন্য ওয়েট করতে পারে
        async function startSingleUpload(file, card) {
            let progressBar = card.querySelector('.progress-bar');
            let percentText = card.querySelector('.percent-text');
            let sizeText = card.querySelector('.size-text');
            let statusText = card.querySelector('.status-text');
            let cancelBtn = card.querySelector('.cancel-btn');

            // সার্ভার ঘুমাচ্ছে কি না তা আগে চেক করা
            try {
                if (Date.now() - lastAwakeTime >= 10 * 60 * 1000) {
                    statusText.innerText = "Connecting to cloud...";
                    statusText.className = "text-[11px] font-semibold text-yellow-400 status-text tracking-wide";
                }
                await ensureCloudIsAwake(); // সার্ভার পুরোপুরি না জাগা পর্যন্ত আপলোড শুরু হবে না
            } catch(e) {
                handleFailedUpload("Network Error!");
                return;
            }

            // আপলোড শুরু হলে কালার নীল হবে
            progressBar.classList.replace('bg-slate-600', 'bg-blue-500');
            statusText.innerText = "Uploading to Server...";
            statusText.className = "text-[11px] font-semibold text-blue-400 status-text tracking-wide";

            let formData = new FormData();
            formData.append("file", file);

            let xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload/", true);

            // Cancel Button
            cancelBtn.onclick = () => {
                xhr.abort();
                statusText.innerText = "Upload Cancelled";
                statusText.className = "text-[11px] font-semibold text-red-400 status-text tracking-wide";
                progressBar.classList.replace('bg-blue-500', 'bg-red-500');
                cancelBtn.classList.add('hidden');
                
                // ক্যানসেল হলে সাথে সাথে লাইনের পরেরটি শুরু হবে
                isUploading = false;
                processNextUpload();
                
                setTimeout(() => { card.style.display = 'none'; }, 2000);
            };

            xhr.upload.onprogress = function(event) {
                if (event.lengthComputable) {
                    let percentComplete = Math.round((event.loaded / event.total) * 100);
                    let loadedMB = (event.loaded / (1024 * 1024)).toFixed(2);
                    let totalMB = (event.total / (1024 * 1024)).toFixed(2);
                    
                    progressBar.style.width = percentComplete + '%';
                    percentText.innerText = percentComplete + '%';
                    sizeText.innerText = `${loadedMB} MB / ${totalMB} MB`;
                    statusText.innerText = "Uploading to Server...";
                    statusText.className = "text-[11px] font-semibold text-blue-400 status-text tracking-wide";
                    
                    if (percentComplete === 100) {
                        statusText.innerText = "Processing in cloud ☁️";
                        statusText.className = "text-[11px] font-semibold text-yellow-400 status-text tracking-wide animate-pulse";
                        cancelBtn.classList.add('hidden');
                    }
                }
            };

            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        let result = JSON.parse(xhr.responseText);
                        if (result.status === "success") {
                            statusText.innerText = "Saved Successfully!";
                            statusText.className = "text-[11px] font-semibold text-green-400 status-text tracking-wide";
                            progressBar.classList.replace('bg-blue-500', 'bg-green-500');
                            
                            db.ref('users/' + currentUser.uid + '/files').push({
                                file_name: result.file_name,
                                file_size: result.file_size,
                                message_id: result.message_id,
                                timestamp: firebase.database.ServerValue.TIMESTAMP
                            });

                            setTimeout(() => { card.style.display = 'none'; }, 3000);
                            finishUploadTask(); // সফল হলে লাইনের পরেরটি শুরু হবে
                            return;
                        }
                    } catch(e) {
                        handleFailedUpload("Server waking up. Retry!");
                        return;
                    }
                }
                handleFailedUpload("Upload Failed!");
            };

            xhr.onerror = function() {
                handleFailedUpload("Network Error!");
            };

            xhr.send(formData);

            function finishUploadTask() {
                isUploading = false;
                processNextUpload();
            }

            function handleFailedUpload(msg) {
                statusText.innerText = msg;
                statusText.className = "text-[11px] font-semibold text-red-400 status-text tracking-wide";
                progressBar.classList.replace('bg-blue-500', 'bg-red-500');
                cancelBtn.classList.add('hidden');
                
                finishUploadTask(); // ফেইল হলেও লাইনের পরেরটি শুরু হবে
                
                // আপলোড ফেইল হলে ৪ সেকেন্ড পর অটো রিমুভ
                setTimeout(() => { card.style.display = 'none'; }, 4000);
            }
        }

        // 6. Realtime Database Fetch & Render (Native Card UI)
        function loadFilesRealtime() {
            let fileList = document.getElementById('fileList');
            let countBadge = document.getElementById('fileCountBadge');

            db.ref('users/' + currentUser.uid + '/files').on('value', (snapshot) => {
                fileList.innerHTML = '';
                
                if (!snapshot.exists()) {
                    countBadge.innerText = "0 Items";
                    fileList.innerHTML = `
                        <div class="flex flex-col items-center justify-center py-10 opacity-50">
                            <i class="fa-solid fa-folder-open text-5xl text-slate-500 mb-4"></i>
                            <p class="text-slate-400 text-sm">No files uploaded yet.</p>
                        </div>
                    `;
                    return;
                }
                
                let data = [];
                snapshot.forEach(child => { data.push({key: child.key, ...child.val()}); });
                data.sort((a, b) => b.timestamp - a.timestamp);
                
                countBadge.innerText = `${data.length} Items`;

                data.forEach(f => {
                    let sizeMB = (f.file_size / (1024 * 1024)).toFixed(2);
                    
                    // Native App Card Style
                    fileList.innerHTML += `
                        <div class="bg-slate-800 p-3 rounded-2xl border border-slate-700 flex justify-between items-center shadow-sm">
                            <div class="flex items-center overflow-hidden flex-1 mr-3">
                                <div class="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center text-blue-500 mr-3 flex-shrink-0">
                                    <i class="fa-solid fa-file text-xl"></i>
                                </div>
                                <div class="overflow-hidden">
                                    <p class="font-semibold text-white text-sm truncate w-full selectable" title="${f.file_name}">${f.file_name}</p>
                                    <p class="text-xs text-slate-400 mt-0.5">${sizeMB} MB</p>
                                </div>
                            </div>
                            
                            <div class="flex items-center gap-1 flex-shrink-0">
                                <button onclick="safeDownload(this, '${f.message_id}')" class="w-10 h-10 rounded-full flex items-center justify-center text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 active:bg-slate-600 transition" title="Download">
                                    <i class="fa-solid fa-arrow-down"></i>
                                </button>
                                <button onclick="deleteFile('${f.key}', ${f.message_id})" class="w-10 h-10 rounded-full flex items-center justify-center text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 active:bg-red-500/30 transition" title="Delete">
                                    <i class="fa-solid fa-trash-can text-sm"></i>
                                </button>
                            </div>
                        </div>
                    `;
                });
            });
        }

        // 7. Universal Cloud Wake-up System (Master Function)
        let lastAwakeTime = 0; 

        function showToast(msg) {
            let toast = document.getElementById('toastNotification');
            if(toast) {
                document.getElementById('toastMessage').innerText = msg;
                toast.classList.remove('opacity-0', '-translate-y-10');
                toast.classList.add('opacity-100', 'translate-y-0');
            }
        }

        function hideToast() {
            let toast = document.getElementById('toastNotification');
            if(toast) {
                toast.classList.remove('opacity-100', 'translate-y-0');
                toast.classList.add('opacity-0', '-translate-y-10');
            }
        }

        // এই ফাংশন আপলোড, ডাউনলোড এবং ডিলিট করার আগে চেক করবে সার্ভার জাগানো আছে কিনা
        async function ensureCloudIsAwake() {
            if (Date.now() - lastAwakeTime < 10 * 60 * 1000) return true; // ১০ মিনিটের ভেতর থাকলে অলরেডি সচল

            let serverResponded = false;
            let toastTimer = setTimeout(() => {
                if (!serverResponded) showToast("Connecting to cloud...");
            }, 1000);

            try {
                let res = await fetch('/ping');
                serverResponded = true;
                clearTimeout(toastTimer);
                hideToast();
                
                lastAwakeTime = Date.now();
                if (!(res.ok && res.headers.get("content-type") && res.headers.get("content-type").includes("application/json"))) {
                    await new Promise(r => setTimeout(r, 2000)); // Render পেজ আসলে ২ সেকেন্ড ওয়েট
                }
                return true;
            } catch(e) {
                clearTimeout(toastTimer);
                hideToast();
                throw new Error("Network error.");
            }
        }

        // 8. Smart Download Logic
        function triggerDownload(url) {
            let a = document.createElement('a');
            a.href = url;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        async function safeDownload(btnElement, messageId) {
            let icon = btnElement.querySelector('i');
            let originalIconClass = icon.className;
            icon.className = "fa-solid fa-arrow-down fa-bounce text-blue-400";
            btnElement.disabled = true;

            try {
                await ensureCloudIsAwake(); // সার্ভার চেক বা জাগানোর মাস্টার কল
                triggerDownload(`/download/${messageId}`);
            } catch(e) {
                alert("Network error. Please check your connection.");
            } finally {
                setTimeout(() => {
                    icon.className = originalIconClass;
                    btnElement.disabled = false;
                }, 1000);
            }
        }

        // 9. Smart Delete Logic
        async function deleteFile(dbKey, messageId) {
            if(!confirm("Delete this file permanently?")) return;
            try {
                showToast("Deleting...");
                await ensureCloudIsAwake(); // সার্ভার চেক বা জাগানোর মাস্টার কল
                await fetch(`/delete/${messageId}`, { method: 'DELETE' });
                db.ref(`users/${currentUser.uid}/files/${dbKey}`).remove();
                hideToast();
            } catch(e) {
                hideToast();
                alert("Error deleting file.");
            }
        }
    </script>
</body>
</html>
"""

@app.get("/ping")
async def ping_server():
    return {"status": "awake"}

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
            # স্লট ফাঁকা হওয়া মাত্রই অটোমেটিক ওয়েটিং থেকে পরের ফাইল এখানে ঢুকে যাবে
            async with download_semaphore: 
                try:
                    async for chunk in bot.stream_media(message, offset=start, limit=(end - start + 1)):
                        # ইউজার ব্রাউজার থেকে ডাউনলোড ক্যানসেল বা পজ করলে সাথে সাথে কানেকশন ব্রেক হবে
                        if await request.is_disconnected():
                            print("User canceled the download. Releasing slot for the next waiting file...")
                            break
                        yield chunk
                except asyncio.CancelledError:
                    # FastAPI ক্লায়েন্ট ডিসকানেক্ট হলে এই এরর দেয়, এটি ধরা মানে স্লট সাথে সাথে ফ্রি করে দেওয়া
                    print("Download task was canceled by browser. Slot freed.")
                except Exception as e:
                    print(f"Stream interrupted: {e}")

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

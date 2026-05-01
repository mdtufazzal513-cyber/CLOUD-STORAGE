import asyncio
from pyrogram import Client

# ====================================================
# ⚙️ CENTRALIZED PROJECT CONFIGURATION ⚙️
# আপনার প্রজেক্টের সব সিক্রেট ডাটা এখন এই একটিমাত্র ফাইলে থাকবে
# ====================================================

API_ID = 33445387
API_HASH = "5b1badf6d0f44c940a2263cef28d6689"

# টেলিগ্রাম বট টোকেন (নতুন সেশন বানাতে কাজে লাগবে)
BOT_TOKEN = "8781052287:AAEYTaE5Cj1sR4dokfsdhlTKXg1t5Kgejd0"

# আপনার জেনারেট করা সেশন স্ট্রিং
SESSION_STRING = "BQH-VgsAjXAtpA7_8WzYjaImZMmoFJUd6RFEut4X32b15iWR-62IjLNTLZQt1xYigp13Sm6rcUVvXEuUdpoJDhwkaSTOCcT2CWGtRPslhvdY7JueDWhne_rJtCSqoV0AcADg21xCGuDNjLl4LaIry4VQerxgYEOmD93djo0MPUZRxoHuEAcNxTrCxr_IqC6fzEsMxB5Mqk1nnNM_-ZBsNKSzfvCiCljgVktNXXilhmchvLTFXs2EvYSHewxyJRuTK-NAVupaUKywQE1hVNWKMmJNKdIbXdPzGFbITV4wdY54ezBTsd1pP-NfLGb_VJYUkaQmeEy5EP49-Ak8gSkZL4AbrMqFKAAAAAIE58I1AA"

# টেলিগ্রাম চ্যানেল আইডি যেখানে ফাইল সেভ হবে
CHANNEL_ID = -1003984468691

# Firebase Admin UID (একাধিক অ্যাডমিন থাকলে কমা দিয়ে লিখবেন)
ADMIN_UIDS = "oAK6oVAdUBetVRBKkbwnUKsHr8A2"


# ====================================================
# 🚀 SESSION GENERATOR LOGIC 
# (এই ফাইলটি রান করলে নিচের কোডগুলো কাজ করবে)
# ====================================================
async def main():
    print("Connecting to Telegram to generate a new session...")
    
    # বট টোকেন দিয়ে লগইন করে সেশন জেনারেট করা
    bot = Client(
        "my_bot_session", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        bot_token=BOT_TOKEN, 
        in_memory=True
    )
    
    await bot.start()
    session_string = await bot.export_session_string()
    
    print("\n\n" + "="*60)
    print("✅ SUCCESS! COPY THE SESSION STRING BELOW:")
    print("="*60 + "\n")
    print(session_string) 
    print("\n" + "="*60 + "\n")
    print("☝️ উপর থেকে স্ট্রিংটি কপি করে এই ফাইলের SESSION_STRING এর জায়গায় বসিয়ে দিন।")
    
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

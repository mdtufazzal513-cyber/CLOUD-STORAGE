import asyncio
from pyrogram import Client

# ==========================================
# ⚙️ CENTRALIZED PROJECT CONFIGURATION ⚙️
# ==========================================
API_ID = 33445387
API_HASH = "5b1badf6d0f44c940a2263cef28d6689"
BOT_TOKEN = "8781052287:AAEYTaE5Cj1sR4dokfsdhlTKXg1t5Kgejd0"
SESSION_STRING = "BQH-VgsAjXAtpA7_8WzYjaImZMmoFJUd6RFEut4X32b15iWR-62IjLNTLZQt1xYigp13Sm6rcUVvXEuUdpoJDhwkaSTOCcT2CWGtRPslhvdY7JueDWhne_rJtCSqoV0AcADg21xCGuDNjLl4LaIry4VQerxgYEOmD93djo0MPUZRxoHuEAcNxTrCxr_IqC6fzEsMxB5Mqk1nnNM_-ZBsNKSzfvCiCljgVktNXXilhmchvLTFXs2EvYSHewxyJRuTK-NAVupaUKywQE1hVNWKMmJNKdIbXdPzGFbITV4wdY54ezBTsd1pP-NfLGb_VJYUkaQmeEy5EP49-Ak8gSkZL4AbrMqFKAAAAAIE58I1AA"
CHANNEL_ID = -1003984468691

# Admin Panel UIDs (একাধিক এডমিন থাকলে কমা দিয়ে লিখবেন)
ADMIN_UIDS = "oAK6oVAdUBetVRBKkbwnUKsHr8A2"


# ==========================================
# SESSION GENERATOR LOGIC (Run this to get session)
# ==========================================
async def main():
    print("Connecting to Telegram...")
    bot = Client("my_bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
    await bot.start()
    session_string = await bot.export_session_string()
    
    print("\n\n" + "="*50)
    print("SUCCESS! COPY THE TEXT BELOW:")
    print("="*50 + "\n")
    print(session_string)
    print("\n" + "="*50 + "\n")
    
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

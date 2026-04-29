from pyrogram import Client
import asyncio

API_ID = 33445387 # আপনার API ID
API_HASH = "5b1badf6d0f44c940a2263cef28d6689"
BOT_TOKEN = "8781052287:AAFi5-uN_mBRZKjeeA0ije0E2mlUrdTQJ0s"

async def main():
    bot = Client("my_bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
    await bot.start()
    session_string = await bot.export_session_string()
    print("\n\n--- আপনার SESSION STRING ---")
    print(session_string)
    print("---------------------------\n\n")
    await bot.stop()

asyncio.run(main())

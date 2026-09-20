import os
import asyncio
import yt_dlp
from time import time
from pyrogram import Client, filters
from pyrogram.types import Message
from youtube_search import YoutubeSearch
import requests
from ShrutixMusic import app
from ShrutixMusic.platforms.Youtube import download_song as yt_api_download_song

# Define a dictionary to track the last message timestamp for each user
user_last_message_time = {}
user_command_count = {}

# Define the threshold for command spamming (e.g., 2 commands within 5 seconds)
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

def safe_remove(file_path):
    """Safely remove a file if it exists"""
    try:
        if file_path and os.path.exists(file_path) and os.path.isfile(file_path):
            os.remove(file_path)
    except Exception as e:
        pass

# Command to search and download song
@app.on_message(filters.command("song"))
async def download_song(_, message: Message):
    user_id = message.from_user.id
    current_time = time()
    
    # Spam protection: Prevent multiple commands within a short time
    last_message_time = user_last_message_time.get(user_id, 0)
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(f"{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ ᴅᴏ sᴘᴀᴍ, ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ")
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time
    
    # Extract query from the message
    query = " ".join(message.command[1:])
    if not query:
        await message.reply("🔗 ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ꜱᴏɴɢ ɴᴀᴍᴇ ᴏʀ ᴜʀʟ ᴛᴏ ꜱᴇᴀʀᴄʜ ꜰᴏʀ 🖇")
        return

    # Searching for the song using YouTubeSearch
    m = await message.reply("🔍ꜱᴇᴀʀᴄʜɪɴɢ...🔎")
    
    ydl_opts = {
        "format": "bestaudio[ext=m4a]",  # Options to download audio in m4a format
        "noplaylist": True,  # Don't download playlists
        "quiet": True,
        "no_warnings": True,
        "logtostderr": False,
        "skip_unavailable_fragments": True,
        "js_runtimes": {"node": {}},  # yt-dlp expects dict format
    }
    
    audio_file = None
    thumb_name = None
    
    try:
        # Search for the song
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            await m.edit("😮‍💨 ɴᴏ ʀᴇꜱᴜʟᴛꜱ ꜰᴏᴜɴᴅ. ᴘʟᴇᴀꜱᴇ ᴍᴀᴋᴇ ꜱᴜʀᴇ ʏᴏᴜ ᴛʏᴘᴇᴅ ᴛʜᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴏɴɢ ɴᴀᴍᴇ ⚠️")
            return

        link = f"https://youtube.com{results[0]['url_suffix']}"
        title = results[0]["title"]
        thumbnail = results[0]["thumbnails"][0]
        thumb_name = f"{title}.jpg"
        
        # Download thumbnail with error handling
        try:
            thumb = requests.get(thumbnail, allow_redirects=True, timeout=10)
            if thumb.status_code == 200:
                open(thumb_name, "wb").write(thumb.content)
        except Exception as thumb_err:
            print(f"Thumbnail download failed: {thumb_err}")
            thumb_name = None
        
        duration = results[0]["duration"]
        views = results[0]["views"]
        channel_name = results[0]["channel"]

        # First try API-backed downloader (no cookies needed)
        await m.edit("💫 ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...💫")
        audio_file = await yt_api_download_song(link)

        # Fallback to yt-dlp only if API fails
        if not audio_file:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info_dict = ydl.extract_info(link, download=False)
                        if not info_dict:
                            await m.edit("❌ Failed to extract video information")
                            return
                        audio_file = ydl.prepare_filename(info_dict)
                        ydl.download([link])
                    except Exception as extract_err:
                        error_msg = str(extract_err).lower()
                        if "unavailable" in error_msg or "age" in error_msg:
                            await m.edit("⚠️ Video unavailable or age-restricted")
                        elif "cookie" in error_msg or "login" in error_msg:
                            await m.edit("🔐 Source website requires login")
                        elif "javascript" in error_msg:
                            await m.edit("⚠️ YouTube requires JavaScript runtime")
                        else:
                            await m.edit(f"❌ Download failed: {str(extract_err)[:100]}")
                        return
            except Exception as ydl_err:
                await m.edit(f"❌ Download error: {str(ydl_err)[:100]}")
                return

        # Verify audio file exists and has content
        if not audio_file or not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
            await m.edit("❌ Downloaded file is empty or missing")
            safe_remove(audio_file)
            return

        # Parsing duration (in seconds)
        dur = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration.split(":"))))
        
        # Sending the audio to the user
        await m.edit("😍 ᴜᴘʟᴏᴀᴅɪɴɢ...🎉")
        await message.reply_audio(
            audio_file,
            thumb=thumb_name if thumb_name and os.path.exists(thumb_name) else None,
            title=title,
            caption=f"{title}\nʀᴇQᴜᴇꜱᴛᴇᴅ ʙʏ ➪ {message.from_user.mention}\nᴠɪᴇᴡꜱ ➪ {views}\nᴄʜᴀɴɴᴇʟ ➪ {channel_name}",
            duration=dur
        )

        await m.delete()

    except Exception as e:
        error_msg = str(e).lower()
        if "no such file" in error_msg:
            await m.edit("❌ Downloaded file not found on disk")
        elif "unavailable" in error_msg:
            await m.edit("⚠️ Video content unavailable")
        else:
            await m.edit("🙂 ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!")
        print(f"Song download error: {str(e)}")
    
    finally:
        # Cleanup downloaded files
        if audio_file:
            safe_remove(audio_file)
        if thumb_name:
            safe_remove(thumb_name)

  

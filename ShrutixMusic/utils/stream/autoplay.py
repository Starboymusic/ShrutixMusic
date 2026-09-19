# ShrutixMusic/utils/stream/autoplay.py
from ShrutixMusic import YouTube, nand
from ShrutixMusic.misc import db
from ShrutixMusic.platforms.Youtube import get_autoplay
from ShrutixMusic.utils.database import get_lang, is_autoplay
from ShrutixMusic.utils.formatters import seconds_to_min
from ShrutixMusic.utils.rich_stream import send_now_playing_rich
from ShrutixMusic.utils.stream.history import record_played, was_recently_played
from ShrutixMusic.utils.stream.queue import put_queue
from ShrutixMusic.utils.thumbnails import get_thumb
from strings import get_string

_pending = {}


async def _first_downloadable(chat_id, tracks, video: bool):
    while tracks:
        track = tracks.pop(0)
        next_id = track.get("video_id")
        if not next_id or was_recently_played(chat_id, next_id):
            continue

        title = (track.get("title") or "Autoplay Track").title()
        duration_min = seconds_to_min(track.get("duration") or 0)

        file_path, direct = await YouTube.download(
            next_id, None, video=video, videoid=True
        )
        if file_path:
            return next_id, title, duration_min, file_path, direct

    return None


async def try_autoplay(chat_id, popped) -> bool:
    if not popped:
        return False

    if not await is_autoplay(chat_id):
        return False

    source_id = popped.get("vidid")
    if not source_id or source_id in ("telegram", "soundcloud"):
        return False

    original_chat_id = popped.get("chat_id")
    video = str(popped.get("streamtype")) == "video"

    cached = _pending.get(chat_id)
    if cached and cached.get("source_id") == source_id:
        pending = cached.get("tracks") or []
    else:
        pending = []

    picked = await _first_downloadable(chat_id, pending, video)

    if not picked:
        try:
            fresh = await get_autoplay(source_id)
        except Exception:
            fresh = []

        pending = [
            track
            for track in fresh
            if track.get("video_id")
            and not was_recently_played(chat_id, track["video_id"])
        ]
        picked = await _first_downloadable(chat_id, pending, video)

    _pending[chat_id] = {"source_id": source_id, "tracks": pending}

    if not picked:
        return False

    next_id, title, duration_min, file_path, direct = picked

    from ShrutixMusic.core.call import Shruti

    try:
        await Shruti.skip_stream(chat_id, file_path, video=video)
    except Exception:
        return False

    record_played(chat_id, next_id)

    await put_queue(
        chat_id,
        original_chat_id,
        file_path if direct else f"vid_{next_id}",
        title,
        duration_min,
        "Autoplay",
        next_id,
        nand.id,
        "video" if video else "audio",
    )

    language = await get_lang(original_chat_id)
    _ = get_string(language)
    img = await get_thumb(next_id)

    run = await send_now_playing_rich(
        nand,
        chat_id,
        original_chat_id,
        img,
        _["stream_1"].format(
            f"https://t.me/{nand.username}?start=info_{next_id}",
            title[:23],
            duration_min,
            "Autoplay",
        ),
    )
    db[chat_id][0]["mystic"] = run
    db[chat_id][0]["markup"] = "stream"
    return True

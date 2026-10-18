import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")

# Лимит Telegram для ботов через облачный API — 50 МБ
MAX_SIZE = 50 * 1024 * 1024

URL_RE = re.compile(r"https?://\S+")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


def download_video(url: str, out_dir: str) -> Path:
    """Синхронная загрузка через yt-dlp (запускается в отдельном потоке)."""
    opts = {
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        # лучшее mp4 до 50 МБ, иначе лучшее что есть с ограничением размера
        "format": (
            "best[ext=mp4][filesize<50M]/"
            "best[ext=mp4][filesize_approx<50M]/"
            "bv*[ext=mp4][height<=720]+ba[ext=m4a]/"
            "best[height<=720]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        if not path.exists():
            path = path.with_suffix(".mp4")
        return path


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Отправь мне ссылку на видео из TikTok, YouTube, "
        "Instagram, Twitter/X, VK, Pinterest и других сайтов — "
        "я пришлю тебе видео."
    )


@dp.message(F.text.regexp(URL_RE))
async def handle_link(message: Message, bot: Bot):
    url = URL_RE.search(message.text).group(0)
    status = await message.answer("⏳ Скачиваю...")

    with tempfile.TemporaryDirectory() as tmp:
        try:
            loop = asyncio.get_running_loop()
            path = await loop.run_in_executor(None, download_video, url, tmp)

            if not path.exists():
                await status.edit_text("❌ Не удалось скачать видео (возможно, оно слишком большое).")
                return

            if path.stat().st_size > MAX_SIZE:
                await status.edit_text("❌ Видео больше 50 МБ — Telegram не даёт ботам отправлять такие файлы.")
                return

            await bot.send_chat_action(message.chat.id, "upload_video")
            await message.answer_video(
                FSInputFile(path),
                caption="✅ Готово!",
                supports_streaming=True,
            )
            await status.delete()

        except yt_dlp.utils.DownloadError as e:
            logging.warning("Download error: %s", e)
            await status.edit_text("❌ Не получилось скачать. Проверь ссылку — видео может быть приватным или недоступным.")
        except Exception:
            logging.exception("Unexpected error")
            await status.edit_text("❌ Произошла ошибка, попробуй ещё раз позже.")


@dp.message()
async def other(message: Message):
    await message.answer("Отправь ссылку на видео 🔗")


async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

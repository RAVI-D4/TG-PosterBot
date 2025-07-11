import logging
import os
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
AUTH_USER_IDS = [
    int(os.getenv("AUTH_USER_ID_1")),
    int(os.getenv("AUTH_USER_ID_2")),
]

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await update.message.reply_text("Sorry, tu authorized nahi hai is bot ko use karne ke liye.")
        return
    await update.message.reply_text(
        "Welcome! Movie, TV show ya series ka naam bhej, mai poster bhej dunga."
    )

async def search_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await update.message.reply_text("Sorry, tu authorized nahi hai is bot ko use karne ke liye.")
        return

    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Bhai, movie ya TV show ka naam toh bhej.")
        return

    try:
        url = f"{TMDB_BASE_URL}/search/multi?api_key={TMDB_API_KEY}&query={query}&language=en-US&page=1"
        response = requests.get(url)
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            await update.message.reply_text("Koi result nahi mila is query ke liye.")
            return

        valid_results = [
            r for r in results[:3] if r.get("media_type") in ["movie", "tv"]
        ]

        if not valid_results:
            await update.message.reply_text("Koi movie ya TV show nahi mila.")
            return

        if len(valid_results) == 1:
            await send_poster(update, context, valid_results[0])
        else:
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"{r['title' if r['media_type'] == 'movie' else 'name']} ({r.get('release_date', r.get('first_air_date', ''))[:4]})",
                        callback_data=f"{r['media_type']}:{r['id']}",
                    )
                ]
                for r in valid_results
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Multiple results mile. Ek choose kar:", reply_markup=reply_markup
            )

    except requests.RequestException as e:
        logger.error(f"TMDB se data fetch karne me error: {e}")
        await update.message.reply_text("Kuch error hua data fetch karte waqt. Thodi der baad try kar.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await query.message.reply_text("Sorry, tu authorized nahi hai is bot ko use karne ke liye.")
        return

    media_type, media_id = query.data.split(":")
    try:
        url = f"{TMDB_BASE_URL}/{media_type}/{media_id}?api_key={TMDB_API_KEY}&language=en-US"
        response = requests.get(url)
        response.raise_for_status()
        media = response.json()
        await send_poster(update, context, media)
    except requests.RequestException as e:
        logger.error(f"Media details fetch karne me error: {e}")
        await query.message.reply_text("Details fetch karne me error hua. Thodi der baad try kar.")

async def send_poster(update: Update, context: ContextTypes.DEFAULT_TYPE, media: dict) -> None:
    title = media.get("title", media.get("name", "Unknown"))
    release_date = media.get("release_date", media.get("first_air_date", "N/A"))[:4]
    overview = media.get("overview", "Koi description nahi hai.")
    poster_path = media.get("poster_path")

    caption = f"**{title} ({release_date})**\n{overview}"

    if poster_path:
        poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}"
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=poster_url,
                caption=caption[:1024],
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Poster bhejne me error: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{caption}\n\nPoster nahi bhej saka, kuch error hua.",
                parse_mode="Markdown",
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{caption}\n\nIs media ka koi poster nahi mila.",
            parse_mode="Markdown",
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} se error hua: {context.error}")
    if update:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Kuch unexpected error hua. Thodi der baad try kar.",
        )

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_media))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

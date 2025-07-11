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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
AUTH_USER_IDS = [
    int(os.getenv("AUTH_USER_ID_1")),
    int(os.getenv("AUTH_USER_ID_2")),
]

# TMDB API base URL
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
    await update.message.reply_text(
        "Welcome! Send me the name of a movie, TV show, or series to get its poster."
    )

async def search_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user queries for movies/TV shows."""
    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Please provide a movie or TV show name.")
        return

    try:
        # Search TMDB for movies and TV shows
        url = f"{TMDB_BASE_URL}/search/multi?api_key={TMDB_API_KEY}&query={query}&language=en-US&page=1"
        response = requests.get(url)
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            await update.message.reply_text("No results found for your query.")
            return

        # Filter results to movies and TV shows, limit to 3
        valid_results = [
            r for r in results[:3] if r.get("media_type") in ["movie", "tv"]
        ]

        if not valid_results:
            await update.message.reply_text("No movies or TV shows found.")
            return

        if len(valid_results) == 1:
            # Single result: send poster directly
            await send_poster(update, context, valid_results[0])
        else:
            # Multiple results: show selection buttons
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
                "Multiple results found. Please select one:", reply_markup=reply_markup
            )

    except requests.RequestException as e:
        logger.error(f"Error fetching data from TMDB: {e}")
        await update.message.reply_text("An error occurred while fetching data. Please try again later.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button selections."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in AUTH_USER_IDS:
        await query.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    media_type, media_id = query.data.split(":")
    try:
        # Fetch detailed information for selected media
        url = f"{TMDB_BASE_URL}/{media_type}/{media_id}?api_key={TMDB_API_KEY}&language=en-US"
        response = requests.get(url)
        response.raise_for_status()
        media = response.json()
        await send_poster(update, context, media)
    except requests.RequestException as e:
        logger.error(f"Error fetching media details: {e}")
        await query.message.reply_text("An error occurred while fetching details. Please try again later.")

async def send_poster(update: Update, context: ContextTypes.DEFAULT_TYPE, media: dict) -> None:
    """Send the poster and media details."""
    title = media.get("title", media.get("name", "Unknown"))
    release_date = media.get("release_date", media.get("first_air_date", "N/A"))[:4]
    overview = media.get("overview", "No description available.")
    poster_path = media.get("poster_path")

    caption = f"**{title} ({release_date})**\n{overview}"

    if poster_path:
        poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}"
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=poster_url,
                caption=caption[:1024],  # Telegram caption limit
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error sending poster: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{caption}\n\nPoster unavailable due to an error.",
                parse_mode="Markdown",
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{caption}\n\nNo poster available for this media.",
            parse_mode="Markdown",
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors globally."""
    logger.error(f"Update {update} caused error {context.error}")
    if update:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An unexpected error occurred. Please try again later.",
        )

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_media))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

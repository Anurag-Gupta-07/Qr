import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your QR Code Reader Bot.\n\n"
        "Use /READQRCODE to start reading a QR code."
    )

# /READQRCODE command handler
async def handle_next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_qr'] = True
    prompt_message = (
        "🌟 **Please send your QR code photo** 📷\n\n"
        "Our bot will read it and provide you with the text or URL encoded in the QR code."
    )
    await update.message.reply_text(prompt_message, parse_mode="Markdown")

# Handler for received photos
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_qr'):
        # If not awaiting a QR code, ignore the photo or provide a default response
        await update.message.reply_text("📷 Please use the /READQRCODE command to read a QR code.")
        return

    user = update.message.from_user
    chat_id = update.message.chat_id

    try:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        file_id = photo.file_id

        # Get file path
        file = await context.bot.get_file(file_id)
        file_path = file.file_path
        file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_path}"

        # Download the image
        image_response = requests.get(file_url)
        if image_response.status_code != 200:
            await update.message.reply_text("❌ Error: Unable to download the image.")
            return

        # Upload to ImgBB
        imgbb_api_url = "https://api.imgbb.com/1/upload"
        imgbb_api_key = os.getenv('IMGBB_API_KEY')  # Use environment variable

        files = {
            'image': image_response.content
        }
        payload = {
            'key': imgbb_api_key
        }

        imgbb_response = requests.post(imgbb_api_url, files=files, data=payload)

        if imgbb_response.status_code == 200:
            imgbb_image_url = imgbb_response.json()['data']['url']

            # Decode QR Code
            qr_api_url = f"https://qrredaes.nepcoderdevs.workers.dev/?url={imgbb_image_url}"
            qr_response = requests.get(qr_api_url)

            if qr_response.status_code == 200:
                raw_text = qr_response.json().get("raw_text", "")

                if raw_text:
                    await update.message.reply_text(
                        f"🔍 **Extracted Text from QR Code:**\n\n<code>{raw_text}</code>",
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text("❌ Error: No text found in the QR code.")
            else:
                await update.message.reply_text("❌ Error: Failed to decode the QR code.")
        else:
            await update.message.reply_text("❌ Error: Failed to upload image to ImgBB.")

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

    finally:
        # Reset the state
        context.user_data['awaiting_qr'] = False

def main():
    # Use environment variable for the bot token
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not bot_token:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable")

    application = ApplicationBuilder().token(bot_token).build()

    # Register command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('READQRCODE', handle_next_command))

    # Register message handler for photos
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
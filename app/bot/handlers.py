import logging
from pathlib import Path

from telegram import InputFile, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.core.keyboards import (
    CHANNEL_KEYBOARD,
    MAIN_MENU,
    USAGE_MENU,
    download_file_type_keyboard,
    download_quality_keyboard,
    result_keyboard,
)
from app.db.session import SessionLocal
from app.services.downloader import DownloadTooLargeError, MaterialDownloader
from app.services.generator import MaterialGenerator
from app.services.image_similarity import ImageMaterialAnalyzer
from app.services.material_search import MaterialSearchService
from app.services.repository import Repository
from app.services.schemas import MaterialResult
from app.services.stats import StatsService

LOGGER = logging.getLogger(__name__)

(
    WAITING_MATERIAL_NAME,
    WAITING_DESCRIPTION,
    WAITING_GENERATION,
    WAITING_BROADCAST,
    WAITING_SIMILAR_IMAGE,
) = range(5)


def register_handlers(application: Application) -> None:
    conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Material Name$"), ask_material_name),
            MessageHandler(filters.Regex("^Describe Material$"), ask_description),
            MessageHandler(filters.Regex("^Generate Material with AI$"), ask_generation),
            MessageHandler(filters.Regex("^Find Similar by Image$"), ask_similar_image),
            CommandHandler("broadcast", ask_broadcast),
        ],
        states={
            WAITING_MATERIAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_material_name)],
            WAITING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            WAITING_GENERATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_generation)],
            WAITING_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            WAITING_SIMILAR_IMAGE: [MessageHandler(filters.PHOTO, handle_similar_image)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(conversation)
    application.add_handler(MessageHandler(filters.Regex("^Material Usage$"), usage_menu))
    application.add_handler(MessageHandler(filters.Regex("^Telegram Channel$"), channel))
    application.add_handler(MessageHandler(filters.Regex("^Favorites$"), favorites))
    application.add_handler(MessageHandler(filters.Regex("^Help$"), help_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_free_text))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _touch(update, context)
    await update.effective_message.reply_text(
        "Welcome to AI Material Assistant.\n\nHow would you like to find your material?",
        reply_markup=MAIN_MENU,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _touch(update, context)
    await update.effective_message.reply_text(
        "Send a material name, describe a surface, choose an application, upload a reference image, "
        "or generate a procedural PBR material.\n\n"
        "Examples:\n"
        "- Walnut wood\n"
        "- Dark concrete with small golden particles\n"
        "- Concrete for brutalist facade\n"
        "- I need a luxury hotel lobby floor",
        reply_markup=MAIN_MENU,
    )


async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Join the Yasr Designs Telegram channel:",
        reply_markup=CHANNEL_KEYBOARD,
    )


async def ask_material_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Enter a material name, for example: Walnut wood")
    return WAITING_MATERIAL_NAME


async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Describe the material: color, finish, style, and surface qualities.")
    return WAITING_DESCRIPTION


async def ask_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "Describe the material to generate, for example: Burned dark oak with gold veins."
    )
    return WAITING_GENERATION


async def ask_similar_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "Upload a clear material photo or render. I will find similar downloadable PBR materials."
    )
    return WAITING_SIMILAR_IMAGE


async def usage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _touch(update, context)
    await update.effective_message.reply_text("Choose the architectural application:", reply_markup=USAGE_MENU)


async def handle_material_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _search_and_render(update, context, update.effective_message.text)
    return ConversationHandler.END


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _search_and_render(update, context, update.effective_message.text)
    return ConversationHandler.END


async def handle_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _generate_and_send(update, context, update.effective_message.text)
    return ConversationHandler.END


async def handle_similar_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    message = update.effective_message
    if not user or not message.photo:
        await message.reply_text("Please upload a material image.")
        return WAITING_SIMILAR_IMAGE

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    photo = message.photo[-1]
    file = await photo.get_file()
    image_dir = Path("generated") / "image-search"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / f"{user.id}-{photo.file_unique_id}.jpg"
    await file.download_to_drive(custom_path=image_path)

    analyzer: ImageMaterialAnalyzer = context.application.bot_data["image_analyzer"]
    query = analyzer.analyze(image_path)
    await message.reply_text(f"I analyzed the image as: {query}\nSearching similar materials now.")
    await _search_and_render(update, context, query)
    return ConversationHandler.END


async def smart_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _search_and_render(update, context, update.effective_message.text)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    if data.startswith("usage:"):
        await handle_usage(update, context, data.split(":", 1)[1])
    elif data.startswith("save:"):
        await save_material(update, context, data.split(":", 1)[1])
    elif data.startswith("more:"):
        await more_like_this(update, context, data.split(":", 1)[1])
    elif data.startswith("variant:"):
        await variant_prompt(update, context, data.split(":", 1)[1])
    elif data.startswith("preview:"):
        await send_material_preview(update, context, data.split(":", 1)[1])
    elif data.startswith("dlopts:"):
        await show_download_options(update, context, data.split(":", 1)[1])
    elif data.startswith("dlquality:"):
        _, material_id, quality = data.split(":", 2)
        await show_file_type_options(update, context, material_id, quality)
    elif data.startswith("dlfile:"):
        _, material_id, quality, file_type = data.split(":", 3)
        await send_material_file(update, context, material_id, quality, file_type)
    elif data.startswith("dl:"):
        _, material_id, quality = data.split(":", 2)
        await send_material_download(update, context, material_id, quality)
    elif data.startswith("nodl:"):
        await update.effective_message.reply_text(
            "This source did not provide a direct bot-downloadable file for that material. "
            "Try Find Similar or Generate Variant."
        )


async def handle_usage(update: Update, context: ContextTypes.DEFAULT_TYPE, usage: str) -> None:
    message = update.effective_message
    consultant = context.application.bot_data["consultant"]
    recommendations = consultant.recommendations_for_usage(usage)
    await message.reply_text(
        f"For {usage}, I recommend: {', '.join(recommendations[:5])}.\n\n"
        "I will search free PBR sources for suitable options."
    )
    await _search_and_render(update, context, " ".join(recommendations[:3]), usage=usage)
    user_id = update.effective_user.id if update.effective_user else None
    await context.application.bot_data["stats"].event(user_id, "usage", {"usage": usage})


async def variant_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, material_id: str) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Please search again.")
        return
    prompt = f"{material.name}, architectural PBR material variant"
    await _generate_and_send(update, context, prompt)


async def _generate_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    generator: MaterialGenerator = context.application.bot_data["generator"]
    stats: StatsService = context.application.bot_data["stats"]
    user = update.effective_user
    message = update.effective_message
    if not user:
        return
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    try:
        package = await generator.generate(prompt, user.id)
        await stats.event(user.id, "generate", {"prompt": prompt})
        await message.reply_photo(
            photo=InputFile(package.maps["albedo"]),
            caption="Preview: generated albedo/base-color map.",
        )
        await message.reply_document(
            document=InputFile(package.maps["zip"]),
            filename=Path(package.maps["zip"]).name,
            caption=(
                f"Generated PBR map package for: {prompt}\n\n"
                "Includes albedo, normal, roughness, height, and ambient occlusion.\n\n"
                f"{package.notes}"
            ),
        )
    except Exception:
        LOGGER.exception("Material generation failed")
        await message.reply_text(
            "I could not generate the material package on this server. "
            "Please try a shorter prompt, or try again in a moment."
        )


async def _search_and_render(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    usage: str | None = None,
) -> None:
    await _touch(update, context)
    message = update.effective_message
    user_id = update.effective_user.id if update.effective_user else None
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    stats: StatsService = context.application.bot_data["stats"]
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    intent, results, note = await search_service.search(text, usage=usage)
    await stats.event(user_id, "search", {"query": text, "intent": intent.search_query})
    await message.reply_text(note)
    for material in results[:4]:
        await _send_material_card(message, context, search_service, material)


async def _send_material_card(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    search_service: MaterialSearchService,
    material: MaterialResult,
) -> None:
    short_id = search_service.short_id(material.key)
    match_percent = min(99, max(1, int(round(material.score * 100))))
    caption = (
        f"*{_escape(material.name)}*\n"
        f"Match: {_escape(str(match_percent))}%\n"
        f"Source: {_escape(material.source)}\n"
        f"Category: {_escape(material.category)}\n"
        f"Recommended usage: {_escape(', '.join(material.recommended_usage))}\n"
        f"Resolution: {_escape(material.resolution or 'varies')}\n"
        f"Files: {_escape('Preview + PBR ZIP' if material.has_direct_downloads else 'Preview only')}"
    )
    keyboard = result_keyboard(short_id, bool(material.preview_url), material.has_direct_downloads)
    if material.preview_url:
        try:
            downloader: MaterialDownloader = context.application.bot_data["downloader"]
            preview_path = await downloader.fetch_preview(material.preview_url, f"{short_id}_preview.jpg")
            await message.reply_photo(
                photo=InputFile(preview_path),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
            return
        except Exception:
            LOGGER.info("Preview failed for %s; sending text card", material.key)
    await message.reply_text(caption, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)


async def show_download_options(update: Update, context: ContextTypes.DEFAULT_TYPE, material_id: str) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material or not material.downloads:
        await update.effective_message.reply_text("No direct ZIP downloads are available for this material.")
        return
    await update.effective_message.reply_text(
        f"Choose quality for {material.name}:",
        reply_markup=download_quality_keyboard(material_id, material.downloads),
    )


async def show_file_type_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    material_id: str,
    quality: str,
) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Search again and download from the new card.")
        return
    files = material.map_downloads.get(quality) or {}
    if not files:
        await send_material_download(update, context, material_id, quality)
        return
    await update.effective_message.reply_text(
        f"{material.name}\nQuality: {quality}\nChoose the file to receive inside Telegram:",
        reply_markup=download_file_type_keyboard(material_id, quality, files),
    )


async def send_material_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, material_id: str) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material or not material.preview_url:
        await update.effective_message.reply_text("Preview file is not available for this material.")
        return

    message = update.effective_message
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    downloader: MaterialDownloader = context.application.bot_data["downloader"]
    filename = f"{material.name.replace(' ', '_')}_preview.jpg"
    try:
        preview_path = await downloader.fetch_preview(material.preview_url, filename)
        await message.reply_document(
            document=InputFile(preview_path),
            filename=preview_path.name,
            caption=f"{material.name}\nPreview JPG",
        )
    except Exception:
        LOGGER.exception("Preview download failed for %s", material.key)
        await message.reply_text("I could not fetch the preview file right now. Try Find Similar.")


async def send_material_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    material_id: str,
    quality: str,
) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Search again and download from the new card.")
        return
    download_url = material.downloads.get(quality)
    if not download_url:
        await update.effective_message.reply_text("That quality is not available for this material.")
        return

    message = update.effective_message
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    downloader: MaterialDownloader = context.application.bot_data["downloader"]
    filename = f"{material.name.replace(' ', '_')}_{quality}.zip"
    try:
        local_zip = await downloader.fetch_zip(download_url, filename)
        await message.reply_document(
            document=InputFile(local_zip),
            filename=local_zip.name,
            caption=f"{material.name}\nQuality: {quality}\nSource: {material.source}",
        )
    except DownloadTooLargeError:
        await message.reply_text(
            f"This {quality} ZIP is too large for the free bot server to upload directly. "
            "Try 1K or 2K."
        )
    except TelegramError:
        LOGGER.exception("Telegram upload failed for %s", material.key)
        await message.reply_text(
            "Telegram could not upload this ZIP directly. Try a lower quality."
        )
    except Exception:
        LOGGER.exception("Download failed for %s", material.key)
        await message.reply_text(
            "I could not fetch this material ZIP from the source right now. Try another quality or Find Similar."
        )


async def send_material_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    material_id: str,
    quality: str,
    file_type: str,
) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Search again and download from the new card.")
        return
    files = material.map_downloads.get(quality) or {}
    file_url = files.get(file_type)
    if not file_url:
        await update.effective_message.reply_text("That file is not available for this material.")
        return

    extension = "zip" if file_type == "zip" else "jpg"
    filename = f"{material.name.replace(' ', '_')}_{quality}_{file_type}.{extension}"
    message = update.effective_message
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    downloader: MaterialDownloader = context.application.bot_data["downloader"]
    try:
        local_file = await downloader.fetch_file(file_url, filename, max_mb=settings.max_bot_download_mb)
        await message.reply_document(
            document=InputFile(local_file),
            filename=local_file.name,
            caption=f"{material.name}\nQuality: {quality}\nFile: {file_type.replace('_', ' ').title()}",
        )
    except DownloadTooLargeError:
        await message.reply_text(f"This {quality} file is too large to upload directly. Try 1K or 2K.")
    except Exception:
        LOGGER.exception("Material file download failed for %s", material.key)
        await message.reply_text("I could not fetch this file right now. Try another file type or quality.")


async def save_material(update: Update, context: ContextTypes.DEFAULT_TYPE, material_id: str) -> None:
    user = update.effective_user
    if not user:
        return
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Search again and save it from the new card.")
        return
    async with SessionLocal() as session:
        saved = await Repository(session).save_favorite(user.id, material)
    await update.effective_message.reply_text("Saved to favorites." if saved else "Already in favorites.")


async def favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    async with SessionLocal() as session:
        items = await Repository(session).favorites_for_user(user.id)
    if not items:
        await update.effective_message.reply_text("No favorites yet. Save materials from any result card.")
        return
    lines = ["Your saved materials:"]
    for item in items:
        lines.append(f"- {item.material_name} ({item.source})")
    await update.effective_message.reply_text("\n\n".join(lines))


async def more_like_this(update: Update, context: ContextTypes.DEFAULT_TYPE, material_id: str) -> None:
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    material = search_service.get_cached(material_id)
    if not material:
        await update.effective_message.reply_text("That result expired. Please search again.")
        return
    await _search_and_render(update, context, material.name)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.effective_message.reply_text("Admin access required.")
        return
    async with SessionLocal() as session:
        stats = await Repository(session).stats()
    await update.effective_message.reply_text(
        "Bot statistics:\n"
        f"Users: {stats['users']}\n"
        f"Searches: {stats['searches']}\n"
        f"Generations: {stats['generations']}\n"
        f"Favorites: {stats['favorites']}\n"
        f"Events: {stats['events']}"
    )


async def ask_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        await update.effective_message.reply_text("Admin access required.")
        return ConversationHandler.END
    await update.effective_message.reply_text("Send the broadcast message, or /cancel.")
    return WAITING_BROADCAST


async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_admin(update):
        return ConversationHandler.END
    text = update.effective_message.text
    async with SessionLocal() as session:
        user_ids = await Repository(session).all_user_ids()
    sent = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            sent += 1
        except TelegramError:
            LOGGER.info("Broadcast failed for user %s", user_id)
    await update.effective_message.reply_text(f"Broadcast sent to {sent}/{len(user_ids)} users.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelled.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


async def _touch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats: StatsService = context.application.bot_data["stats"]
    await stats.touch_user(update.effective_user)


def _is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in settings.admin_id_set)


def _escape(value: str) -> str:
    chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in chars else char for char in value)

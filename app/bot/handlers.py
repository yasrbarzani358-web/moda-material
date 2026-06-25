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
from app.core.keyboards import MAIN_MENU, USAGE_MENU, result_keyboard
from app.db.session import SessionLocal
from app.services.generator import MaterialGenerator
from app.services.material_search import MaterialSearchService
from app.services.repository import Repository
from app.services.schemas import MaterialResult
from app.services.stats import StatsService

LOGGER = logging.getLogger(__name__)

WAITING_MATERIAL_NAME, WAITING_DESCRIPTION, WAITING_GENERATION, WAITING_BROADCAST = range(4)


def register_handlers(application: Application) -> None:
    conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔍 Material Name$"), ask_material_name),
            MessageHandler(filters.Regex("^📝 Describe Material$"), ask_description),
            MessageHandler(filters.Regex("^🎨 Generate Material with AI$"), ask_generation),
            CommandHandler("broadcast", ask_broadcast),
        ],
        states={
            WAITING_MATERIAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_material_name)],
            WAITING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            WAITING_GENERATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_generation)],
            WAITING_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(conversation)
    application.add_handler(MessageHandler(filters.Regex("^🏠 Material Usage$"), usage_menu))
    application.add_handler(MessageHandler(filters.Regex("^⭐ Favorites$"), favorites))
    application.add_handler(MessageHandler(filters.Regex("^❓ Help$"), help_command))
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
        "Send a material name, describe a surface, choose an application, or ask for AI generation.\n\n"
        "Examples:\n"
        "• Walnut wood\n"
        "• Dark concrete with small golden particles\n"
        "• Concrete for brutalist facade\n"
        "• I need a luxury hotel lobby floor",
        reply_markup=MAIN_MENU,
    )


async def ask_material_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Enter a material name, for example: Walnut wood")
    return WAITING_MATERIAL_NAME


async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Describe the material: color, finish, style, and surface qualities.")
    return WAITING_DESCRIPTION


async def ask_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Describe the material to generate, for example: Burned dark oak with gold veins.")
    return WAITING_GENERATION


async def usage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _touch(update, context)
    await update.effective_message.reply_text("Choose the architectural application:", reply_markup=USAGE_MENU)


async def handle_material_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _search_and_render(update, context, update.effective_message.text)
    return ConversationHandler.END


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _search_and_render(update, context, update.effective_message.text)
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


async def handle_usage(update: Update, context: ContextTypes.DEFAULT_TYPE, usage: str) -> None:
    message = update.effective_message
    search_service: MaterialSearchService = context.application.bot_data["search_service"]
    consultant = context.application.bot_data["consultant"]
    recommendations = consultant.recommendations_for_usage(usage)
    await message.reply_text(
        f"For {usage}, I recommend: {', '.join(recommendations[:5])}.\n\n"
        "I’ll also search free PBR sources for suitable options."
    )
    await _search_and_render(update, context, " ".join(recommendations[:3]), usage=usage)
    user_id = update.effective_user.id if update.effective_user else None
    await context.application.bot_data["stats"].event(user_id, "usage", {"usage": usage})
    _ = search_service


async def handle_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _generate_and_send(update, context, update.effective_message.text)
    return ConversationHandler.END


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
    package = await generator.generate(prompt, user.id)
    await stats.event(user.id, "generate", {"prompt": prompt})
    await message.reply_document(
        document=InputFile(package.maps["zip"]),
        filename=Path(package.maps["zip"]).name,
        caption=f"Generated PBR maps for: {prompt}\n\n{package.notes}",
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
    for material in results[:6]:
        await _send_material_card(message, search_service, material)


async def _send_material_card(message, search_service: MaterialSearchService, material: MaterialResult) -> None:
    short_id = search_service.short_id(material.key)
    caption = (
        f"*{_escape(material.name)}*\n"
        f"Source: {_escape(material.source)}\n"
        f"Category: {_escape(material.category)}\n"
        f"Recommended usage: {_escape(', '.join(material.recommended_usage))}\n"
        f"Resolution: {_escape(material.resolution or 'varies')}\n"
        f"[Open material]({material.page_url})"
    )
    keyboard = result_keyboard(short_id, material.download_url or material.page_url)
    if material.preview_url:
        try:
            await message.reply_photo(
                photo=material.preview_url,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
            return
        except TelegramError:
            LOGGER.info("Preview failed for %s; sending text card", material.key)
    await message.reply_text(caption, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)


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
        url = item.download_url or "#"
        lines.append(f"• {item.material_name} ({item.source})\n{url}")
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

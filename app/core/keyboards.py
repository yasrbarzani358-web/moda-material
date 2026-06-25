from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🔍 Material Name", "📝 Describe Material"],
        ["🏠 Material Usage", "🎨 Generate Material with AI"],
        ["⭐ Favorites", "❓ Help"],
    ],
    resize_keyboard=True,
)

USAGE_MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Floor", callback_data="usage:floor"),
            InlineKeyboardButton("Wall", callback_data="usage:wall"),
            InlineKeyboardButton("Roof", callback_data="usage:roof"),
        ],
        [
            InlineKeyboardButton("Door", callback_data="usage:door"),
            InlineKeyboardButton("Ceiling", callback_data="usage:ceiling"),
            InlineKeyboardButton("Furniture", callback_data="usage:furniture"),
        ],
        [
            InlineKeyboardButton("Exterior", callback_data="usage:exterior"),
            InlineKeyboardButton("Interior", callback_data="usage:interior"),
            InlineKeyboardButton("Facade", callback_data="usage:facade"),
        ],
    ]
)


def result_keyboard(material_id: str, download_url: str | None) -> InlineKeyboardMarkup:
    buttons = []
    if download_url:
        buttons.append([InlineKeyboardButton("Download", url=download_url)])
    buttons.append(
        [
            InlineKeyboardButton("More Like This", callback_data=f"more:{material_id}"),
            InlineKeyboardButton("Save", callback_data=f"save:{material_id}"),
        ]
    )
    buttons.append([InlineKeyboardButton("Generate Variant", callback_data=f"variant:{material_id}")])
    return InlineKeyboardMarkup(buttons)

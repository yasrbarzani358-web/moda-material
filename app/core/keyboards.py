from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["Material Name", "Describe Material"],
        ["Material Usage", "Find Similar by Image"],
        ["Generate Material with AI", "Telegram Channel"],
        ["Favorites", "Help"],
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

CHANNEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Open Telegram Channel", url="https://t.me/yasrdesigns")]]
)


def result_keyboard(material_id: str, has_preview: bool = False, has_direct_downloads: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    download_row = []
    if has_preview:
        download_row.append(InlineKeyboardButton("JPG Preview", callback_data=f"preview:{material_id}"))
    if has_direct_downloads:
        download_row.append(InlineKeyboardButton("PBR / ZIP Package", callback_data=f"dlopts:{material_id}"))
    if download_row:
        buttons.append(download_row)
    else:
        buttons.append([InlineKeyboardButton("No Direct Files", callback_data=f"nodl:{material_id}")])
    buttons.append(
        [
            InlineKeyboardButton("Find Similar", callback_data=f"more:{material_id}"),
            InlineKeyboardButton("Save", callback_data=f"save:{material_id}"),
        ]
    )
    buttons.append([InlineKeyboardButton("Generate Variant", callback_data=f"variant:{material_id}")])
    return InlineKeyboardMarkup(buttons)


def download_quality_keyboard(material_id: str, downloads: dict[str, str]) -> InlineKeyboardMarkup:
    order = {"1K": 1, "2K": 2, "4K": 4, "8K": 8, "SOURCE": 99}
    rows = []
    for quality in sorted(downloads.keys(), key=lambda item: order.get(item, 100)):
        rows.append([InlineKeyboardButton(f"{quality}", callback_data=f"dlquality:{material_id}:{quality}")])
    return InlineKeyboardMarkup(rows)


def download_file_type_keyboard(material_id: str, quality: str, files: dict[str, str]) -> InlineKeyboardMarkup:
    labels = {
        "diffuse": "Diffuse Map",
        "normal": "Normal Map",
        "roughness": "Roughness Map",
        "displacement": "Displacement Map",
        "ao": "Ambient Occlusion",
        "zip": "PBR ZIP Package",
    }
    rows = []
    for key in ["diffuse", "normal", "roughness", "displacement", "ao", "zip"]:
        if key in files:
            rows.append([InlineKeyboardButton(labels[key], callback_data=f"dlfile:{material_id}:{quality}:{key}")])
    return InlineKeyboardMarkup(rows)

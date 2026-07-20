# ==========================
# IMPORTLAR
# ==========================
import os
import re
import requests
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from database import init_db, add_user, get_user_count, get_today_count, get_users_page
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==========================
# TOKENLAR
# ==========================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REMOVE_BG_API = os.getenv("REMOVE_BG_API")


def _parse_admin_ids(raw: str) -> set[int]:
    ids = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            continue
    return ids


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
PAGE_SIZE = 20


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ==========================
# PAPKALAR
# ==========================
os.makedirs("photos", exist_ok=True)

# ==========================
# HOLATLAR
# ==========================
PHOTO, SIZE, LIMIT, ACTION = range(4)

# ==========================
# START
# ==========================
ADMIN_MENU_START = "🏠 /start"
ADMIN_MENU_USERS = "👥 Foydalanuvchilar soni"
ADMIN_MENU_USERLIST = "📋 Foydalanuvchilar ro'yxati"
ADMIN_MENU_SETTINGS = "⚙️ Sozlamalar"

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [ADMIN_MENU_START, ADMIN_MENU_USERS],
        [ADMIN_MENU_USERLIST, ADMIN_MENU_SETTINGS],
    ],
    resize_keyboard=True,
)

USER_KEYBOARD = ReplyKeyboardMarkup(
    [[ADMIN_MENU_START]],
    resize_keyboard=True,
)


async def notify_admins_of_new_user(context: ContextTypes.DEFAULT_TYPE, user):
    username = f"@{user.username}" if user.username else "—"
    text = (
        "🆕 Yangi foydalanuvchi!\n\n"
        f"ID: {user.id}\n"
        f"Username: {username}\n"
        f"Ism: {user.first_name or '—'}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            continue


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new_user = add_user(user.id, user.username, user.first_name)
    keyboard = ADMIN_KEYBOARD if is_admin(user.id) else USER_KEYBOARD
    await update.message.reply_text(
        "👋 Salom!\n\n"
        "Bu bot Ramziddin Parpiyev tomonidan ishlab chiqarilgan.\n\n"
        "Menga rasm yuboring.\n\n"
        "Men quyidagilarni qila olaman:\n\n"
        "🖼 O'lchamni o'zgartirish\n"
        "📦 Hajmini kamaytirish\n"
        "✂️ Orqa fonni transparent qilish\n\n"
        "Rasm yuboring.",
        reply_markup=keyboard,
    )
    if is_new_user:
        await notify_admins_of_new_user(context, user)

# ==========================
# ADMIN: FOYDALANUVCHILAR SONI
# ==========================
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    count = get_user_count()
    await update.message.reply_text(f"👥 Jami foydalanuvchilar: {count}")

# ==========================
# ADMIN: FOYDALANUVCHILAR RO'YXATI
# ==========================
def _format_user_line(row):
    user_id, username, first_name, joined_at = row
    uname = f"@{username}" if username else "—"
    name = first_name or "—"
    date = joined_at[:10] if joined_at else "—"
    return f"ID: {user_id} | {uname} | {name} | {date}"


def _build_userlist_page(offset):
    rows = get_users_page(offset, PAGE_SIZE)
    total = get_user_count()
    text = (
        "\n".join(_format_user_line(row) for row in rows)
        if rows
        else "Foydalanuvchilar topilmadi."
    )

    buttons = []
    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        buttons.append(InlineKeyboardButton("⬅️ Oldinga", callback_data=f"userlist:{prev_offset}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"userlist:{offset + PAGE_SIZE}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None
    return text, markup


async def userlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    text, markup = _build_userlist_page(0)
    await update.message.reply_text(text, reply_markup=markup)


async def userlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    offset = int(query.data.split(":", 1)[1])
    text, markup = _build_userlist_page(offset)
    await query.edit_message_text(text, reply_markup=markup)

# ==========================
# ADMIN: SETTINGS PANEL
# ==========================
async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="settings:stats")],
        [InlineKeyboardButton("👥 Foydalanuvchilar ro'yxati", callback_data="settings:userlist")],
    ])
    await update.message.reply_text("⚙️ Admin panel", reply_markup=keyboard)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    if query.data == "settings:stats":
        total = get_user_count()
        today = get_today_count()
        await query.edit_message_text(f"📊 Statistika\n\nJami: {total}\nBugun: {today}")
    elif query.data == "settings:userlist":
        text, markup = _build_userlist_page(0)
        await query.edit_message_text(text, reply_markup=markup)

# ==========================
# RASM QABUL QILISH (Gruppa + Private uchun yangilandi)
# ==========================
ACTION_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("1️⃣ O'lchamni o'zgartirish", callback_data="action:resize")],
    [InlineKeyboardButton("2️⃣ Fonni transparent qilish", callback_data="action:transparent")],
    [InlineKeyboardButton("3️⃣ Ikkalasini ham (Fon + O'lcham)", callback_data="action:both")],
    [InlineKeyboardButton("❌ Bekor qilish", callback_data="flow:cancel")],
])

CANCEL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Bekor qilish", callback_data="flow:cancel")],
])


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    user_id = update.effective_user.id
    path = f"photos/{user_id}.jpg"

    await file.download_to_drive(path)
    context.user_data["photo"] = path
    context.user_data["chat_id"] = update.effective_chat.id  # Guruh yoki private chatni saqlash

    await update.message.reply_text(
        "Rasm qabul qilindi ✅\n\nNima qilamiz?",
        reply_markup=ACTION_KEYBOARD,
    )
    return ACTION
# ==========================
# ACTION TANLASH
# ==========================
async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "flow:cancel":
        await query.edit_message_text("❌ Jarayon bekor qilindi. Yangi rasm yuboring.")
        return ConversationHandler.END

    if choice == "action:resize":
        context.user_data["mode"] = "resize"
        await query.edit_message_text(
            "O'lchamni kiriting (width x height).\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE

    if choice == "action:both":
        context.user_data["mode"] = "both"
        await query.edit_message_text(
            "O'lchamni kiriting (width x height).\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE

    if choice == "action:transparent":
        await query.edit_message_text("⏳ Fon olib tashlanmoqda...")
        input_file = context.user_data["photo"]
        output_file = f"photos/{query.from_user.id}_transparent.png"

        result = remove_background(input_file, output_file)

        if result:
            await query.message.reply_document(
                document=open(output_file, "rb"),
                filename="transparent.png",
                caption="✅ Fon transparent qilindi.",
            )
        else:
            await query.message.reply_text("❌ Fon olib tashlashda xatolik yuz berdi.")
        return ConversationHandler.END

    # Unrecognized callback_data — should be unreachable given the handler's
    # pattern, but fail loudly instead of silently running background removal.
    await query.edit_message_text("❌ Noma'lum tanlov. Iltimos, /start bilan qaytadan boshlang.")
    return ConversationHandler.END


async def cancel_to_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "photo" not in context.user_data:
        await query.edit_message_text("Iltimos, rasmni qaytadan yuboring.")
        return ConversationHandler.END
    await query.edit_message_text(
        "Rasm qabul qilindi ✅\n\nNima qilamiz?",
        reply_markup=ACTION_KEYBOARD,
    )
    return ACTION


# ==========================
# REMOVE.BG FUNKSIYA
# ==========================
def remove_background(input_file, output_file):
    try:
        with open(input_file, "rb") as image:
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": image},
                data={"size": "auto"},
                headers={"X-Api-Key": REMOVE_BG_API}
            )
        
        if response.status_code == 200:
            with open(output_file, "wb") as out:
                out.write(response.content)
            return True
        else:
            print("Remove.bg xatosi:", response.text)
            return False
    except Exception as e:
        print("Xatolik:", e)
        return False


# ==========================
# SIZE
# ==========================
async def resize_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r"^\d+x\d+$", text):
        await update.message.reply_text(
            "❌ Noto'g'ri format.\n\nMisol:\n512x512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return SIZE

    width, height = map(int, text.split("x"))
    context.user_data["width"] = width
    context.user_data["height"] = height

    await update.message.reply_text(
        "Endi maksimal hajmini KB da yozing.\n\n"
        "Misol:\n512",
        reply_markup=CANCEL_KEYBOARD,
    )
    return LIMIT


# ==========================
# LIMIT + Rasmni qayta ishlash
# ==========================
async def resize_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "Faqat son yozing.\nMisol: 512",
            reply_markup=CANCEL_KEYBOARD,
        )
        return LIMIT
    
    max_kb = int(text)
    input_file = context.user_data["photo"]
    width = context.user_data["width"]
    height = context.user_data["height"]
    mode = context.user_data.get("mode")

    # Agar 3-tanlov bo'lsa (Fon + Resize)
    if mode == "both":
        await update.message.reply_text("⏳ Fon olib tashlanmoqda...")
        transparent_file = f"photos/{update.effective_user.id}_transparent.png"
        result = remove_background(input_file, transparent_file)
        
        if result:
            input_file = transparent_file
        else:
            await update.message.reply_text("❌ Fonni olib tashlashda xatolik.")
            return ConversationHandler.END

    # Rasmni o'lchamini o'zgartirish
    img = Image.open(input_file).convert("RGBA")
    img = img.resize((width, height))
    
    output = BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)

    file_size_kb = round(len(output.getvalue()) / 1024, 1)

    await update.message.reply_document(
        document=output,
        filename="processed.png",
        caption=(
            f"✅ Tayyor!\n\n"
            f"📏 O'lcham: {width}x{height}\n"
            f"💾 Hajmi: {file_size_kb} KB\n"
            f"🖼 Format: PNG Transparent"
        )
    )
    
    return ConversationHandler.END


# ==========================
# CANCEL
# ==========================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Jarayon bekor qilindi.")
    return ConversationHandler.END
# ==========================
# CONVERSATION HANDLER
# ==========================
conv = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.PHOTO & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
            get_photo
        )
    ],
    states={
        ACTION: [
            CallbackQueryHandler(
                action_callback,
                pattern=r"^(action:resize|action:transparent|action:both|flow:cancel)$",
            )
        ],
        SIZE: [
            CallbackQueryHandler(cancel_to_action_selection, pattern=r"^flow:cancel$"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_size
            )
        ],
        LIMIT: [
            CallbackQueryHandler(cancel_to_action_selection, pattern=r"^flow:cancel$"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_limit
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel)
    ],
    per_user=True,          # Har bir foydalanuvchi uchun alohida holat
    per_chat=False
)

# ==========================
# BOTNI ISHGA TUSHIRISH
# ==========================
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("userlist", userlist_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CallbackQueryHandler(userlist_callback, pattern=r"^userlist:"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings:"))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_START]), start))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERS]), users_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_USERLIST]), userlist_cmd))
    app.add_handler(MessageHandler(filters.Text([ADMIN_MENU_SETTINGS]), settings_cmd))
    app.add_handler(conv)

    print("🤖 Bot muvaffaqiyatli ishga tushdi... Guruhlar va shaxsiy chatlar uchun tayyor!")
    app.run_polling()

if __name__ == "__main__":
    main()
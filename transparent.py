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
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        "👋 Salom!\n\n"
        "Bu bot Ramziddin Parpiyev tomonidan ishlab chiqarilgan.\n\n"
        "Menga rasm yuboring.\n\n"
        "Men quyidagilarni qila olaman:\n\n"
        "🖼 O'lchamni o'zgartirish\n"
        "📦 Hajmini kamaytirish\n"
        "✂️ Orqa fonni transparent qilish\n\n"
        "Rasm yuboring."
    )

# ==========================
# RASM QABUL QILISH (Gruppa + Private uchun yangilandi)
# ==========================
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    user_id = update.effective_user.id
    path = f"photos/{user_id}.jpg"
    
    await file.download_to_drive(path)
    context.user_data["photo"] = path
    context.user_data["chat_id"] = update.effective_chat.id  # Guruh yoki private chatni saqlash

    await update.message.reply_text(
        "Rasm qabul qilindi ✅\n\n"
        "Nima qilamiz?\n\n"
        "1 - O'lchamni o'zgartirish\n"
        "2 - Fonni transparent qilish\n"
        "3 - Ikkalasini ham (Fon + O'lcham)\n\n"
        "1, 2 yoki 3 yozing."
    )
    return ACTION
# ==========================
# ACTION TANLASH
# ==========================
async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "1":
        await update.message.reply_text(
            "O'lchamni kiriting (width x height).\n\n"
            "Misol:\n512x512"
        )
        context.user_data["mode"] = "resize"
        return SIZE
        
    elif text == "2":
        await update.message.reply_text("⏳ Fon olib tashlanmoqda...")
        input_file = context.user_data["photo"]
        output_file = f"photos/{update.effective_user.id}_transparent.png"
        
        result = remove_background(input_file, output_file)
        
        if result:
            await update.message.reply_document(
                document=open(output_file, "rb"),
                filename="transparent.png",
                caption="✅ Fon transparent qilindi."
            )
        else:
            await update.message.reply_text("❌ Fon olib tashlashda xatolik yuz berdi.")
        return ConversationHandler.END
        
    elif text == "3":
        await update.message.reply_text(
            "O'lchamni kiriting (width x height).\n\n"
            "Misol:\n512x512"
        )
        context.user_data["mode"] = "both"
        return SIZE
        
    else:
        await update.message.reply_text("Faqat 1, 2 yoki 3 raqamini yozing.")
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
            "❌ Noto'g'ri format.\n\nMisol:\n512x512"
        )
        return SIZE
    
    width, height = map(int, text.split("x"))
    context.user_data["width"] = width
    context.user_data["height"] = height
    
    await update.message.reply_text(
        "Endi maksimal hajmini KB da yozing.\n\n"
        "Misol:\n512"
    )
    return LIMIT


# ==========================
# LIMIT + Rasmni qayta ishlash
# ==========================
async def resize_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Faqat son yozing.\nMisol: 512")
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
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                action
            )
        ],
        SIZE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS),
                resize_size
            )
        ],
        LIMIT: [
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
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("🤖 Bot muvaffaqiyatli ishga tushdi... Guruhlar va shaxsiy chatlar uchun tayyor!")
    app.run_polling()

if __name__ == "__main__":
    main()
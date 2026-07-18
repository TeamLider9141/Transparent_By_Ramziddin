# Admin panel — foydalanuvchi kuzatuvi va admin komandalari

## Maqsad

Bot `/start` bosgan har bir foydalanuvchini saqlab boradi. Admin(lar) foydalanuvchilar soni va ro'yxatini ko'ra oladi, oddiy user faqat `/start` ishlata oladi.

## Ma'lumotlar bazasi

SQLite, fayl: `users.db`. Bot ishga tushganda avtomatik yaratiladi (`CREATE TABLE IF NOT EXISTS`).

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    joined_at TEXT
);
```

`database.py` moduli:
- `init_db()` — jadval yaratadi, bot startida bir marta chaqiriladi
- `add_user(user_id, username, first_name)` — `INSERT OR IGNORE`, `joined_at` = hozirgi UTC vaqt (ISO format)
- `get_user_count() -> int`
- `get_today_count() -> int` — `joined_at` bugungi sanaga to'g'ri keladiganlar soni
- `get_users_page(offset, limit) -> list[tuple]` — `joined_at DESC` bo'yicha saralab, sahifalab qaytaradi

## Admin autentifikatsiya

`.env` ga qo'shiladi: `ADMIN_IDS=123456789,987654321` (vergul bilan ajratilgan Telegram user_id lar, bo'sh joylar trim qilinadi).

`transparent.py` ichida:
```python
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
```

Admin komandalarining boshida tekshiriladi. Admin bo'lmasa: `"⛔ Bu buyruq faqat admin uchun."` javob qaytadi, funksiya shu yerda to'xtaydi.

## Komandalar

### `/start` (hammaga ochiq, mavjud xatti-harakat saqlanadi)
Qo'shimcha: handler boshida `add_user(user.id, user.username, user.first_name)` chaqiriladi. Qolgan logika o'zgarmaydi.

### `/users` (faqat admin)
`get_user_count()` chaqirib, "👥 Jami foydalanuvchilar: N" deb javob beradi.

### `/userlist` (faqat admin)
Birinchi sahifani (0-19) ko'rsatadi: har user uchun bitta qator — `ID: <user_id> | @<username> | <first_name> | <joined_at sanasi>`. Xabar tagida inline tugmalar: `⬅️ Oldinga` (agar offset > 0) va `Keyingi ➡️` (agar keyingi sahifada user bo'lsa). Callback data formati: `userlist:<offset>`.

Callback query handler (`userlist_callback`) tugma bosilganda offset'ni o'zgartirib, xabarni `edit_message_text` bilan yangilaydi. Admin tekshiruvi bu yerda ham qilinadi (callback query user id orqali).

### `/settings` (faqat admin)
Panel matni + 2 ta inline tugma:
- "📊 Statistika" → callback `settings:stats` — jami va bugungi yangi userlar sonini ko'rsatadi (`get_user_count()`, `get_today_count()`)
- "👥 Foydalanuvchilar ro'yxati" → callback `settings:userlist` — `/userlist` bilan bir xil natijani (0-sahifa, sahifalash tugmalari bilan) chiqaradi

## Fayl o'zgarishlari

- **Yangi:** `database.py`
- **O'zgaradi:** `transparent.py` — yangi importlar (`sqlite3` orqali emas, `database` modulidan), `ADMIN_IDS`/`is_admin`, yangi handlerlar (`users_cmd`, `userlist_cmd`, `settings_cmd`), callback query handler, `main()` ichida yangi handlerlar ro'yxatga olinadi, `init_db()` chaqiriladi
- **O'zgaradi:** `.env`, `.env.example` — `ADMIN_IDS` qatori qo'shiladi
- **O'zgaradi:** `DEPLOY.md` — `.env` bo'limiga `ADMIN_IDS` haqida eslatma
- **O'zgaradi:** `requirements.txt` — o'zgarish shart emas (sqlite3 standart kutubxona)
- **O'zgaradi:** `.gitignore` — `users.db` qo'shiladi (runtime ma'lumot, git'ga tushmasin)

## Xato holatlari

- `ADMIN_IDS` bo'sh yoki noto'g'ri formatda bo'lsa — bot ishga tushadi, lekin hech kim admin komandalarini ishlata olmaydi (xavfsiz default)
- DB fayl yo'q bo'lsa — `init_db()` yaratadi
- `/userlist` va `/settings` callback tugmalarida admin bo'lmagan user callback yuborsa (masalan eski xabarga boshqa user bossa) — callback `answer()` qilinadi lekin xabar o'zgarmaydi

## Test rejasi

- Admin bo'lmagan user `/users`, `/userlist`, `/settings` yozadi → ruxsat yo'q xabari
- Admin `/users` yozadi → to'g'ri son
- Bir nechta user `/start` bosadi, keyin admin `/userlist` → hammasi ro'yxatda, sahifalash tugmalari ishlaydi
- Admin `/settings` → ikkala tugma ham to'g'ri ishlaydi
- Bot qayta ishga tushganda (`users.db` mavjud) — eski ma'lumot yo'qolmaydi, `add_user` dublikat yaratmaydi

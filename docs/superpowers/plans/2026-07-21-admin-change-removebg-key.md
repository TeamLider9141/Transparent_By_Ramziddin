# Admin: remove.bg API key ni bot orqali almashtirish

## Context

remove.bg API keyning oylik limiti tugaganda, hozir keyni almashtirish uchun serverga kirib `.env` ni qo'lda tahrirlab botni restart qilish kerak. Bu noqulay. Adminlar bot ichidan yangi keyni kiritib, `.env` ga yozdirib, restart'siz darhol qo'llay olishi kerak. Xavfsizlik uchun: yangi key remove.bg'da tekshiriladi, tasdiqlanadi, va key yozilgan xabar chatdan o'chiriladi.

## Qarorlar (tasdiqlangan)

1. **Saqlash: `.env` fayl** + xotiradagi global darhol yangilanadi (restart shart emas).
2. **Tekshirish:** saqlashdan oldin `GET https://api.remove.bg/v1.0/account` (header `X-Api-Key`) — 200 = valid, kredit sarflamaydi.
3. **Xavfsizlik:** admin yuborgan key-xabar o'chiriladi; tasdiqda key niqoblanadi (`uwfY...gu04`).

## Muhim texnik faktlar

- `REMOVE_BG_API` — `transparent.py:32` module global, `remove_background()` (`:304`) uni nom orqali o'qiydi → `global REMOVE_BG_API` bilan qayta tayinlash keyingi chaqiruvlarda darhol ishlaydi, restart yo'q.
- `.env` yo'li: `os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")` — CWD'dan qat'i nazar transparent.py yonidagi `.env`ni topadi (serverda `/home/ubuntu/Transparent_By_Ramziddin/.env`).
- `.env` yozish uchun `dotenv.set_key(path, key, value, quote_mode="never")` — mavjud qatorlarni saqlab, faqat `REMOVE_BG_API=` ni almashtiradi, bo'lmasa qo'shadi, faylni yaratadi. Qo'lda parsing shart emas.
- **Routing konflikti:** `main()`da `CallbackQueryHandler(settings_callback, pattern=r"^settings:")` (`:455`) `settings:apikey`ni ham ushlaydi. Yangi `apikey_conv` ni settings handleridan **oldin** ro'yxatga olish kerak (PTB bir guruhda ro'yxat tartibida tekshiradi, birinchi mos keladigan yutadi).

## Fayl o'zgarishlari

Barchasi `transparent.py` (+ testlar):

### Yangi holatlar
`transparent.py:63` — `PHOTO, SIZE, LIMIT, ACTION = range(4)` yoniga: `AWAIT_API_KEY, CONFIRM_API_KEY = range(4, 6)`.

### Yangi helperlar
- `_mask_api_key(key: str) -> str` — 8 belgidan uzun bo'lsa `key[:4] + "..." + key[-4:]`, aks holda `"****"` (qisqa key sizib chiqmaydi).
- `_validate_remove_bg_key(key: str) -> str` — `requests.get("https://api.remove.bg/v1.0/account", headers={"X-Api-Key": key}, timeout=15)`. **3 xil qaytadi:** `200` → `"valid"`; `401`/`403` → `"invalid"`; boshqa status yoki `requests.RequestException` → `"error"`. (invalid keyni tarmoq xatosidan farqlash uchun.)
- `_write_env_value(key, value, path=ENV_PATH)` — atomik `.env` yozuvchi: mavjud qatorlarni o'qiydi (fayl bo'lmasa bo'sh boshlaydi); `#`-izoh va bo'sh qatorlarni tashlab, `line.split("=",1)[0].strip() == key` mos qatorni `f"{key}={value}\n"` bilan almashtiradi (boshqa qatorlar/tartib saqlanadi); mos yo'q bo'lsa oxiriga qo'shadi (oldingi qator `\n` bilan tugashini ta'minlab); `tempfile.mkstemp(dir=...)` → yozish → `os.replace(tmp, path)` (POSIX'da atomik). Qiymat tirnoqsiz yoziladi (mavjud `.env` formatiga mos).
- Modul boshida: `import tempfile`, `ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")`.

### Yangi handlerlar (apikey oqimi)
- `apikey_start(update, context)` — entry (callback `settings:apikey`). `is_admin` tekshir → `query.edit_message_text("🔑 Yangi remove.bg API key ni yuboring:")` → `return AWAIT_API_KEY`.
- `apikey_receive(update, context)` — `AWAIT_API_KEY` holatida text. `key = update.message.text.strip()`. Key-xabarni **darhol** o'chir: `try: await update.message.delete() except Exception: pass`. Agar bo'sh/probelli → xato xabar, `return AWAIT_API_KEY`. `status = _validate_remove_bg_key(key)`: `"error"` → "⚠️ remove.bg bilan bog'lanib bo'lmadi..." `return AWAIT_API_KEY`; `"invalid"` → "❌ Key yaroqsiz..." `return AWAIT_API_KEY`; `"valid"` → `context.user_data["pending_api_key"] = key`, reply masklangan key + inline `[✅ Saqlash (apikey:save)] [❌ Bekor (apikey:cancel)]`, `return CONFIRM_API_KEY`.
- `apikey_save(update, context)` — `CONFIRM_API_KEY`, callback `apikey:save`. `query.answer()`, `is_admin`. `key = context.user_data.pop("pending_api_key", None)`; yo'q bo'lsa → "❌ Key topilmadi" END. `try: _write_env_value("REMOVE_BG_API", key); global REMOVE_BG_API; REMOVE_BG_API = key` (**yozish muvaffaqiyatli bo'lsagina globalni yangila** — yozish xato bersa ishlab turgan key o'zgarmaydi). Xato → "❌ .env yozishda xatolik...". Muvaffaqiyat → "✅ API key yangilandi (restartsiz)." `return ConversationHandler.END`.
- `apikey_cancel(update, context)` — callback `apikey:cancel` (ikkala holatda) va `/cancel` fallback. `context.user_data.pop("pending_api_key", None)`, global tegilmaydi, "❌ Bekor qilindi." `return ConversationHandler.END`.

### settings_cmd
`settings_cmd` (`:180-183`) klaviaturasiga qator qo'sh: `[InlineKeyboardButton("🔑 API key almashtirish", callback_data="settings:apikey")]`.

### ConversationHandler + main()
```python
apikey_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(apikey_start, pattern=r"^settings:apikey$")],
    states={
        AWAIT_API_KEY: [
            CallbackQueryHandler(apikey_cancel, pattern=r"^apikey:cancel$"),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND
                & ~filters.Text([ADMIN_MENU_START, ADMIN_MENU_SETTINGS]),
                apikey_receive,
            ),
        ],
        CONFIRM_API_KEY: [
            CallbackQueryHandler(apikey_save, pattern=r"^apikey:save$"),
            CallbackQueryHandler(apikey_cancel, pattern=r"^apikey:cancel$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", apikey_cancel)],
    per_user=True, per_chat=False, allow_reentry=True,
)
```
`AWAIT_API_KEY` text filtri `ADMIN_MENU_START`/`ADMIN_MENU_SETTINGS` klaviatura tugmalarini chiqarib tashlaydi — aks holda mid-capture'da tugma bosilsa key deb o'qib qolinadi.

`main()`da `app.add_handler(apikey_conv)` ni `CallbackQueryHandler(settings_callback, pattern=r"^settings:")` **dan oldin** qo'sh (routing konflikti: `^settings:` `settings:apikey`ni ham ushlaydi, birinchi ro'yxatga olingan yutadi).

## Xato holatlari

- Bo'sh/probel key → qayta so'raydi.
- Tarmoq xatosi (remove.bg yetib bo'lmadi) → "ulanib bo'lmadi" (invalid'dan farqli), qayta so'raydi.
- Non-admin callback → `apikey_start`/`apikey_confirm` `is_admin` bilan himoyalangan.
- Xabar o'chirish ruxsati yo'q bo'lsa (`delete()` xatosi) → jim o'tadi (`try/except`).

## Test rejasi (`tests/test_apikey.py`, yangi)

- `_mask_key`: uzun key → `uwfY...gu04`; qisqa key → `****`.
- `validate_removebg_key`: `requests.get` monkeypatch → 200 → True; 403 → False; `RequestException` → propagates (raises).
- `save_removebg_key`: tmp `.env` ga `ENV_PATH` monkeypatch → faylga yozilganini + `transparent.REMOVE_BG_API` global yangilanganini tekshir; mavjud boshqa qatorlar saqlanganini tekshir.
- `apikey_start`: admin → `AWAIT_API_KEY` qaytaradi + so'rov xabari; non-admin → himoya.
- `apikey_received`: valid key (validate monkeypatch True) → `CONFIRM_API_KEY`, `pending_api_key` saqlangan, masklangan matn; invalid → `AWAIT_API_KEY`; network error → `AWAIT_API_KEY` + "ulanib bo'lmadi"; key-xabar `delete()` chaqirilgan.
- `apikey_confirm`: `apikey:save` → `save_removebg_key` chaqirilgan (monkeypatch) + END; `apikey:cancel` → END, saqlanmagan.
- Full suite regressiyasiz (hozir 48 test).

## DEPLOY.md eslatma

`.env` service user (`ubuntu`) tomonidan **yoziladigan** bo'lishi kerak (runtime rewrite). systemd unitiga `ProtectHome=`, `ProtectSystem=strict`, yoki loyiha papkasini qamrab oluvchi `ReadOnlyPaths=` qo'shilmasligi kerak — aks holda `.env` yozib bo'lmaydi (feature xato beradi, lekin bot ishlab turadi). Hozirgi unitda sandbox yo'q, muammo yo'q.

## Verification

- `python3 -m pytest -v` — barcha yashil.
- `python3 -c "import ast; ast.parse(open('transparent.py').read())"` — syntax OK.
- Manual (foydalanuvchi serverda): `/settings` → "🔑 API key almashtirish" → key yubor → xabar o'chadi, masklangan tasdiq → "✅ Saqlash" → `.env` yangilanadi, keyingi rasm yangi key bilan ishlaydi. Noto'g'ri key → rad etiladi.

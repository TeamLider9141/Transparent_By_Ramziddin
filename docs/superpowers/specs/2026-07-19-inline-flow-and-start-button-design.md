# Rasm ishlov berish oqimini inline tugmalarga o'tkazish + /start tugmasi

## Maqsad

Hozirgi rasm ishlov berish oqimi (foydalanuvchi rasm yuboradi → 1/2/3 raqamini yozadi → o'lcham/hajm kiritadi) matnga asoslangan. Bu ikkita muammoni keltirib chiqaradi:

1. Foydalanuvchi noto'g'ri qadam bosib qolsa (masalan, o'lcham so'ralayotganda), jarayonni bekor qilib qaytadan boshlash uchun `/cancel` yozishi va rasmni **qaytadan yuborishi** kerak bo'ladi.
2. 1/2/3 tanlovi matn yozishni talab qiladi — tugma orqali tanlash tabiiyroq.

Bundan tashqari, `/start` buyrug'ini ham pastki klaviatura tugmalari qatoriga qo'shish kerak (hozir faqat admin uchun 3 ta tugma bor: Foydalanuvchilar soni/ro'yxati/Sozlamalar; oddiy userda umuman tugma yo'q).

## 1. Rasm qabul qilingandan keyin: inline tugmalar

`get_photo` handleri hozir matn bilan javob beradi ("1 - O'lchamni o'zgartirish\n2 - ...\n3 - ...\n\n1, 2 yoki 3 yozing."). Bu matn saqlanadi, lekin ostiga `InlineKeyboardMarkup` qo'shiladi:

| Tugma matni | callback_data |
|---|---|
| 1️⃣ O'lchamni o'zgartirish | `action:resize` |
| 2️⃣ Fonni transparent qilish | `action:transparent` |
| 3️⃣ Ikkalasini ham (Fon + O'lcham) | `action:both` |
| ❌ Bekor qilish | `flow:cancel` |

`ACTION` holatidagi handler matn o'rniga `CallbackQueryHandler` bo'ladi — endi foydalanuvchi raqam yozishi shart emas, faqat tugma bosadi. Matn bilan "1"/"2"/"3" yozish endi qo'llab-quvvatlanmaydi (ConversationHandler ACTION holatida faqat callback handler bo'ladi, matn handleri olib tashlanadi).

Tanlov mantig'i o'zgarmaydi (resize → SIZE holatiga o'tadi, transparent → darhol ishlov beradi va tugaydi, both → SIZE holatiga o'tadi) — faqat trigger manbasi `update.message.text` o'rniga `query.data` bo'ladi, va javob berish `reply_text` o'rniga `query.edit_message_text` bo'ladi.

## 2. "Bekor qilish" tugmasi — har bosqichda, holatga qarab boshqacha ishlaydi

`flow:cancel` callback_data barcha uchta holatda (`ACTION`, `SIZE`, `LIMIT`) mavjud bo'ladi, lekin har holatda **boshqa handler** unga javob beradi (ConversationHandler holatga qarab callback_data'ni turli funksiyaga yo'naltiradi):

- **`ACTION` holatida** (rasm hali qayta ishlanmagan, tanlov qilinmagan): `flow:cancel` bosilsa → jarayon **to'liq** tugaydi. Xabar: "❌ Jarayon bekor qilindi. Yangi rasm yuboring." `ConversationHandler.END` qaytadi. (Bu hozirgi `/cancel` buyrug'i bilan bir xil natija — funksional dublikat, lekin foydalanuvchi uchun qulayroq kirish nuqtasi.)
- **`SIZE` holatida** (o'lcham so'ralmoqda): `flow:cancel` bosilsa → jarayon **to'liq tugamaydi**. Xuddi shu saqlangan rasm (`context.user_data["photo"]`) bilan qayta 1/2/3 tanlash xabari ko'rsatiladi (yuqoridagi 4 tugma bilan), `ACTION` holatiga qaytadi.
- **`LIMIT` holatida** (max KB so'ralmoqda): xuddi shu — `flow:cancel` bosilsa, saqlangan rasm bilan `ACTION` holatiga qaytadi.

`SIZE`/`LIMIT` holatlaridagi mavjud matn-kiritish xabarlariga ("O'lchamni kiriting...", "Endi maksimal hajmini KB da yozing...") ham `flow:cancel` tugmali `InlineKeyboardMarkup` qo'shiladi.

`SIZE`/`LIMIT` holatlarida mavjud matn handlerlari (`resize_size`, `resize_limit`) **saqlanib qoladi** — bu ikki bosqich hali ham erkin matn kiritishni talab qiladi (o'lcham va KB soni tugma bilan tanlanmaydi, faqat yoziladi). `flow:cancel` uchun qo'shimcha `CallbackQueryHandler` shu holatlarning handler ro'yxatiga **qo'shiladi** (matn handlerini almashtirmaydi).

Mavjud `/cancel` matn buyrug'i (fallback) o'zgarishsiz qoladi — u har doim jarayonni to'liq tugatadi, har qanday holatda.

## 3. "/start" tugmasi pastki klaviaturada

Hozirgi `ADMIN_KEYBOARD` (3 tugma, bittadan qatorda) 2x2 setkaga o'zgaradi va "🏠 /start" qo'shiladi:

```
[🏠 /start]              [👥 Foydalanuvchilar soni]
[📋 Foydalanuvchilar ro'yxati]   [⚙️ Sozlamalar]
```

Oddiy (admin bo'lmagan) foydalanuvchilar hozir umuman pastki klaviatura ko'rmaydi (`reply_markup=None`). Bu o'zgaradi: ular endi bitta tugmali klaviatura ko'radi:

```
[🏠 /start]
```

`main()`ga yangi handler qo'shiladi: `MessageHandler(filters.Text(["🏠 /start"]), start)` — tugma bosilganda xuddi `/start` buyrug'i yozilgandek ishlaydi (mavjud `users_cmd`/`userlist_cmd`/`settings_cmd` tugmalari bilan bir xil naqsh).

## Fayl o'zgarishlari

- **`transparent.py`**:
  - `get_photo`: `InlineKeyboardMarkup` bilan 4 tugma qo'shiladi
  - `action` → `action_callback` ga aylanadi (CallbackQueryHandler, matn o'rniga `query.data` asosida branch qiladi)
  - Yangi: `cancel_to_full_end` (ACTION holatidagi `flow:cancel` uchun) va `cancel_to_action_selection` (SIZE/LIMIT holatidagi `flow:cancel` uchun, saqlangan rasmni qayta ko'rsatadi)
  - `resize_size`, `resize_limit` xabarlariga `flow:cancel` tugmali `InlineKeyboardMarkup` qo'shiladi
  - `conv` ning `states` lug'ati yangilanadi: `ACTION` endi faqat `CallbackQueryHandler`; `SIZE`/`LIMIT` ga qo'shimcha `CallbackQueryHandler(pattern="^flow:cancel$")` qo'shiladi (mavjud matn handleridan oldin)
  - `ADMIN_KEYBOARD` 2x2 setkaga o'zgaradi, `"🏠 /start"` qo'shiladi
  - Yangi: `USER_KEYBOARD` — faqat `"🏠 /start"` tugmali, oddiy userlarga
  - `start()`: `keyboard = ADMIN_KEYBOARD if is_admin(...) else USER_KEYBOARD` (avval `else None` edi)
  - `main()`: yangi `MessageHandler(filters.Text(["🏠 /start"]), start)` ro'yxatga olinadi

## Xato holatlari

- Callback tugma bosilganda foydalanuvchi ma'lumotida (`context.user_data`) saqlangan `photo` yo'qolgan bo'lsa (masalan, bot qayta ishga tushgan, `user_data` xotirada saqlanadi va process restart bo'lsa yo'qoladi) — `cancel_to_action_selection` `context.user_data.get("photo")` orqali tekshiradi; agar yo'q bo'lsa, foydalanuvchiga "Iltimos, rasmni qaytadan yuboring." deb javob beradi va jarayonni tugatadi (`ConversationHandler.END`), xatoga tushmaydi.

## Test rejasi

- `get_photo` javobida 4 ta inline tugma borligini tekshirish (callback_data qiymatlari to'g'ri)
- `action_callback`: har uch tanlov (`action:resize`, `action:transparent`, `action:both`) to'g'ri holatga o'tishini/tugashini tekshirish
- `flow:cancel` ACTION holatida → `ConversationHandler.END` qaytarishini va xabar matnini tekshirish
- `flow:cancel` SIZE holatida → ACTION holatiga qaytishini, xuddi shu rasm bilan 4 tugma qayta ko'rsatilishini tekshirish
- `flow:cancel` LIMIT holatida → xuddi shunday
- `cancel_to_action_selection`: `context.user_data`da `photo` yo'q bo'lganda graceful xabar berishini tekshirish
- `resize_size`/`resize_limit` xabarlarida `flow:cancel` tugmasi borligini tekshirish
- `ADMIN_KEYBOARD`: 2 qator, har birida 2 tugma, "🏠 /start" borligini tekshirish
- `USER_KEYBOARD`: 1 tugma, "🏠 /start" ekanini tekshirish
- `start()`: admin va oddiy user uchun to'g'ri klaviatura tanlanishini tekshirish (mavjud testlar yangilanadi)

# Serverda 24/7 ishga tushirish

Loyiha serverga clone qilingandan keyin botni doimiy (24/7) ishlatish uchun systemd service ishlatiladi — server qayta yonganda ham, bot crash bo'lsa ham avtomatik qayta ko'tariladi.

## 1. Python muhit tayyorlash

```bash
cd /home/ubuntu/Transparent_By_Ramziddin
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. .env fayl yaratish

`.env` fayl `.gitignore` da bo'lgani uchun clone qilinganda kelmaydi — serverda qo'lda yaratish kerak:

```bash
nano .env
```

Ichiga:
```
TELEGRAM_TOKEN=your_telegram_bot_token
REMOVE_BG_API=your_remove_bg_api_key
ADMIN_IDS=123456789,987654321
```

`ADMIN_IDS` — admin bo'ladigan Telegram user_id'lar, vergul bilan ajratiladi. O'z Telegram ID'ingizni bilish uchun @userinfobot ga yozing.

(`.env.example` faylga qarang — qaysi o'zgaruvchilar kerakligi shu yerda ko'rsatilgan.)

## 3. systemd service yaratish

```bash
sudo nano /etc/systemd/system/transparentbot.service
```

Ichiga (yo'llarni va foydalanuvchi nomini o'zingiznikiga moslang):

```ini
[Unit]
Description=Transparent Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Transparent_By_Ramziddin
ExecStart=/home/ubuntu/Transparent_By_Ramziddin/venv/bin/python transparent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Yuqoridagi `User=`, `WorkingDirectory=`, `ExecStart=` qiymatlari — server user `ubuntu` va papka `/home/ubuntu/Transparent_By_Ramziddin` bo'yicha to'ldirilgan. Boshqa server/user bo'lsa, `whoami` va `pwd` natijasiga moslab o'zgartiring. Moslamasangiz systemd xato beradi: `Failed to determine user credentials: No such process` (status=217/USER).

## 4. Ishga tushirish

```bash
sudo systemctl daemon-reload
sudo systemctl enable transparentbot
sudo systemctl start transparentbot
```

`enable` — server reboot bo'lganda ham bot avtomatik ishga tushishini ta'minlaydi.

## 5. Holatni tekshirish / loglarni ko'rish

```bash
sudo systemctl status transparentbot
journalctl -u transparentbot -f
```

## 6. Kodni yangilagandan keyin qayta ishga tushirish

```bash
cd /home/ubuntu/Transparent_By_Ramziddin
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart transparentbot
```

## Muqobil usul (tavsiya etilmaydi)

`screen` yoki `tmux` orqali ham ishga tushirish mumkin, lekin server reboot bo'lganda bot to'xtab qoladi va qo'lda qayta ishga tushirish kerak bo'ladi. Uzoq muddatli 24/7 ishlash uchun systemd usuli ishonchliroq.

## GitHub'dan yangilanishlarni serverga olish (git pull)

Kodga o'zgarish kiritib GitHub'ga push qilgandan keyin, serverdagi nusxani yangilash uchun:

```bash
cd /home/ubuntu/Transparent_By_Ramziddin
git pull origin main
```

Agar `requirements.txt` o'zgargan bo'lsa, paketlarni ham yangilang:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

So'ng botni qayta ishga tushiring, o'zgarishlar kuchga kirishi uchun:

```bash
sudo systemctl restart transparentbot
```

Tekshirish:

```bash
sudo systemctl status transparentbot
journalctl -u transparentbot -f
```

**Eslatma:** `.env` fayl `.gitignore` da bo'lgani uchun `git pull` uni o'zgartirmaydi/o'chirmaydi — u serverda alohida saqlanib qoladi, xavotir olmang.

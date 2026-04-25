import telebot
from telebot import types
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- KONFIGURATSIYA ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7642176910
DB_NAME = 'imperial_v30.db'
PRICE_STARS = 5  # Kimligini bilish narxi (Stars)

# Majburiy obuna kanallar (agar kerak bo'lsa, to'ldiring)
CHANNELS = ["@kanal1", "@kanal2"]  # O'zingizning kanallaringizni qo'shing

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- DATABASE ---
def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=15)

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                          (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, 
                          link_token TEXT, join_date DATETIME, ban_until DATETIME,
                          is_premium INTEGER DEFAULT 0)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER)')
        conn.commit()

def check_sub(uid):
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, uid).status
            if status in ['left', 'kicked']:
                return False
        except:
            continue
    return True

def is_banned(uid):
    with get_db_connection() as conn:
        res = conn.execute('SELECT ban_until FROM users WHERE id = ?', (uid,)).fetchone()
        if res and res[0]:
            try:
                ban_time = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S.%f')
                if datetime.now() < ban_time:
                    return ban_time
            except ValueError:
                try:
                    ban_time = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() < ban_time:
                        return ban_time
                except:
                    return False
    return False

# --- REKLAMA TARQATISH ---
def broadcast_ad(message):
    if message.text == "❌ Bekor qilish":
        bot.send_message(ADMIN_ID, "❌ Bekor qilindi.", reply_markup=main_keyboard(ADMIN_ID))
        return

    with get_db_connection() as conn:
        users = conn.execute('SELECT id FROM users').fetchall()

    bot.send_message(ADMIN_ID, f"🚀 Xabar {len(users)} ta odamga yuborilmoqda...")

    send_count = 0
    for u in users:
        try:
            bot.copy_message(chat_id=u[0], from_chat_id=ADMIN_ID, message_id=message.message_id)
            send_count += 1
        except:
            continue

    bot.send_message(ADMIN_ID, f"✅ Tugadi. {send_count} ta odamga yetib bordi.", reply_markup=main_keyboard(ADMIN_ID))

def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💎 Shaxsiy havola", "👤 Profilim")
    kb.add("ℹ️ Info")
    if uid == ADMIN_ID:
        kb.add("⚙️ Admin Panel")
    return kb

# --- TO'LOV UCHUN INVOICE YUBORISH FUNKSIYASI ---
def send_reveal_invoice(uid, target_id):
    prices = [types.LabeledPrice(label="Kimligini bilish 🕵️", amount=PRICE_STARS)]
    bot.send_invoice(
        uid,
        title="Shaxsni aniqlash",
        description="Botdagi anonim xabarni kim yozganini ko'rish imkonini sotib oling!",
        invoice_payload=f"reveal_{target_id}",
        provider_token="",  # Stars uchun bo'sh
        currency="XTR",
        prices=prices
    )

# --- START ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.chat.id
    if is_banned(uid):
        bot.send_message(uid, "🚫 Siz botdan chetlatilgansiz.")
        return

    first_name = message.from_user.first_name
    full_name = f"{first_name} {message.from_user.last_name or ''}".strip()
    uname = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"

    with get_db_connection() as conn:
        user_data = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()
        if not user_data:
            token = secrets.token_hex(4)
            conn.execute('INSERT INTO users (id, username, full_name, link_token, join_date) VALUES (?, ?, ?, ?, ?)',
                         (uid, uname, full_name, token, datetime.now()))
            conn.commit()

    args = message.text.split()
    if len(args) > 1:
        token_arg = args[1]
        with get_db_connection() as conn:
            target = conn.execute('SELECT id FROM users WHERE link_token = ?', (token_arg,)).fetchone()

        if target and target[0] != uid:
            with get_db_connection() as conn:
                conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target[0]))
                conn.commit()
            bot.send_message(uid, "✨ <b>Siz anonim suhbatga ulandingiz!</b>\nMarhamat, xabaringizni yozing. 🔥",
                             reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))
            return

    welcome_text = (
        f"🌟 <b>Salom, {first_name}! Anonim olamiga xush kelibsiz!</b>\n\n"
        f"1️⃣ O'z shaxsingizni yashirgan holda gaplashishingiz;\n"
        f"2️⃣ Siz haqingizda nima deb o'ylashlarini bilib olishingiz mumkin! 🔥\n\n"
        f"👇 <b>Boshlash uchun tugmalardan foydalaning:</b>"
    )
    bot.send_message(uid, welcome_text, reply_markup=main_keyboard(uid))

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id

    if call.data == "refresh_link":
        new_token = secrets.token_hex(4)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET link_token = ? WHERE id = ?', (new_token, uid))
            conn.commit()
        bot.answer_callback_query(call.id, "Havola yangilandi!")
        link = f"https://t.me/{bot.get_me().username}?start={new_token}"
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🚀 Do'stlarga ulashish", url=f"https://t.me/share/url?url={link}"),
            types.InlineKeyboardButton("🔄 Havolani yangilash", callback_data="refresh_link")
        )
        bot.edit_message_text(f"🔗 <b>Havolangiz:</b>\n\n{link}", uid, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("reply_"):
        target_id = int(call.data.split("_")[1])
        with get_db_connection() as conn:
            conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target_id))
            conn.commit()
        bot.send_message(uid, "✨ <b>Marhamat, javobingizni yozing:</b>",
                         reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))

    elif call.data.startswith("reveal_"):
        target_id = int(call.data.split("_")[1])
        send_reveal_invoice(uid, target_id)
        bot.answer_callback_query(call.id, "To'lov uchun hisob-faktura yuborildi.")

    elif call.data.startswith("report_"):
        parts = call.data.split("_")
        rep_id = parts[1]
        reporter = uid
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_acc_{rep_id}_{reporter}"),
            types.InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_rej_{reporter}_{rep_id}")
        )
        bot.send_message(ADMIN_ID, f"🚩 <b>SHIKOYAT:</b>\nID: <code>{rep_id}</code>\nShikoyatchi: <code>{reporter}</code>", reply_markup=kb)
        bot.answer_callback_query(call.id, "Adminga yuborildi.")

    elif call.data.startswith("adm_acc_"):
        parts = call.data.split("_")
        bad_id = int(parts[2])
        reporter = int(parts[3])
        ban_until = datetime.now() + timedelta(minutes=10)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET ban_until = ? WHERE id = ?', (ban_until, bad_id))
            conn.execute('DELETE FROM active_chats WHERE user_id = ? OR partner_id = ?', (bad_id, bad_id))
            conn.commit()
        try:
            bot.send_message(bad_id, "⚠️ Siz 10 minutga bloklandingiz.")
        except:
            pass
        try:
            bot.send_message(reporter, "✅ Shikoyatingiz tasdiqlandi. Foydalanuvchi bloklandi.")
        except:
            pass
        bot.edit_message_text(f"✅ ID <code>{bad_id}</code> 10 daqiqaga bloklandi.", ADMIN_ID, call.message.message_id)

    elif call.data.startswith("adm_rej_"):
        parts = call.data.split("_")
        reporter = int(parts[2])
        rep_id = int(parts[3])
        try:
            bot.send_message(reporter, "❌ Shikoyatingiz rad etildi.")
        except:
            pass
        bot.edit_message_text(f"❌ ID <code>{rep_id}</code> bo'yicha shikoyat rad etildi.", ADMIN_ID, call.message.message_id)

    elif call.data == "admin_stats":
        with get_db_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            premium = conn.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1').fetchone()[0]
        bot.send_message(ADMIN_ID, f"📊 <b>Statistika:</b>\n\n👥 Jami: {total} ta\n💎 Premium: {premium} ta")

    elif call.data == "admin_ad":
        msg = bot.send_message(ADMIN_ID, "📝 <b>Reklama xabarini (matn/rasm/video) yuboring:</b>",
                               reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Bekor qilish"))
        bot.register_next_step_handler(msg, broadcast_ad)

# --- TO'LOV ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.chat.id
    payload = message.successful_payment.invoice_payload  # "reveal_<target_id>"

    with get_db_connection() as conn:
        conn.execute('UPDATE users SET is_premium = 1 WHERE id = ?', (uid,))
        conn.commit()

    bot.send_message(uid, "✅ <b>Tabriklaymiz!</b> Endi sizga kelgan anonim xabarlarda yuboruvchi kimligini ko'rishingiz mumkin.",
                     reply_markup=main_keyboard(uid))

    # Agar invoice reveal uchun bo'lsa, yuboruvchini ko'rsatish
    if payload.startswith("reveal_"):
        target_id = int(payload.split("_")[1])
        with get_db_connection() as conn:
            sender = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (target_id,)).fetchone()
        if sender:
            sender_name = sender[0]
            sender_username = sender[1] if sender[1] else "yo'q"
            bot.send_message(uid, f"🕵️ <b>Yuboruvchi:</b> {sender_name} (@{sender_username})")

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    if not check_sub(uid) or is_banned(uid):
        return

    if message.text == "💎 Shaxsiy havola":
        with get_db_connection() as conn:
            token = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()[0]
        link = f"https://t.me/{bot.get_me().username}?start={token}"
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🚀 Do'stlarga ulashish", url=f"https://t.me/share/url?url={link}"),
            types.InlineKeyboardButton("🔄 Havolani yangilash", callback_data="refresh_link")
        )
        bot.send_message(uid, f"🔗 <b>Sizning havolangiz:</b>\n\n{link}\n\nMenga anonim xabar yuboring! 😉", reply_markup=kb)

    elif message.text == "👤 Profilim":
        with get_db_connection() as conn:
            user = conn.execute('SELECT join_date, is_premium FROM users WHERE id = ?', (uid,)).fetchone()
        status = "Premium 💎" if user[1] == 1 else "Oddiy 👤"
        join_date = user[0] if user[0] else "Noma'lum"
        bot.send_message(uid, f"👤 <b>Profilingiz:</b>\n\n🆔 ID: <code>{uid}</code>\n📅 Sana: {join_date}\n🌟 Status: {status}")

    elif message.text == "ℹ️ Info":
        bot.send_message(uid, "ℹ️ <b>Ushbu bot orqali sizga anonim tarzda xabarlar yuborishlari mumkin.</b>\nShaxsiy havolangizni tarqating va do'stlaringiz fikrini bilib oling!")

    elif message.text == "⚙️ Admin Panel" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
            types.InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_ad")
        )
        bot.send_message(uid, "👑 <b>Admin Panel</b>", reply_markup=kb)

    elif message.text == "🛑 Suhbatni yakunlash":
        with get_db_connection() as conn:
            conn.execute('DELETE FROM active_chats WHERE user_id = ? OR partner_id = ?', (uid, uid))
            conn.commit()
        bot.send_message(uid, "🔴 Suhbat yakunlandi.", reply_markup=main_keyboard(uid))

    else:
        with get_db_connection() as conn:
            res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()

        if res:
            p_id = res[0]
            with get_db_connection() as conn:
                p_user = conn.execute('SELECT full_name, username, is_premium FROM users WHERE id = ?', (p_id,)).fetchone()

            if not p_user:
                bot.send_message(uid, "⚠️ Foydalanuvchi topilmadi.")
                return

            p_full_name, p_username, p_is_premium = p_user

            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✍️ Javob berish", callback_data=f"reply_{uid}"),
                types.InlineKeyboardButton("⚠️ Shikoyat qilish", callback_data=f"report_{uid}")
            )

            # Agar qabul qiluvchi Premium bo'lmasa, kimligini bilish tugmasi
            if not p_is_premium:
                kb.add(types.InlineKeyboardButton("🔍 Kimligini bilish (Stars ⭐️)", callback_data=f"reveal_{uid}"))

            # Xabarni yuborish
            successful = False
            try:
                bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
                successful = True
            except Exception as e:
                bot.send_message(uid, f"❌ Xabar yuborib bo'lmadi. {str(e)}")
                return

            if successful:
                # Agar qabul qiluvchi Premium bo'lsa, yuboruvchi kimligini ko'rsatish
                if p_is_premium:
                    sender_full = message.from_user.full_name
                    sender_username = message.from_user.username or "yo'q"
                    sender_info = f"🕵️ <b>Yuboruvchi:</b> {sender_full} (@{sender_username})"
                    try:
                        bot.send_message(p_id, sender_info)
                    except:
                        pass

                bot.send_message(uid, "✅ Yuborildi!")

                # ADMIN LOG
                sender_full = message.from_user.full_name
                sender_username = message.from_user.username or "yo'q"

                log_text = (
                    f"📄 <b>XABAR NAZORATI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Yuboruvchi:</b> {sender_full}\n"
                    f"🎭 <b>Username:</b> @{sender_username}\n"
                    f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                    f"──────────────────\n"
                    f"🎯 <b>Qabul qiluvchi:</b> {p_full_name}\n"
                    f"🎭 <b>Username:</b> @{p_username or 'yoq'}\n"
                    f"🆔 <b>ID:</b> <code>{p_id}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━"
                )
                try:
                    bot.send_message(ADMIN_ID, log_text)
                    bot.copy_message(ADMIN_ID, uid, message.message_id)
                except:
                    pass

if __name__ == '__main__':
    init_db()
    print("Bot ishga tushdi...")
    bot.infinity_polling(skip_pending=True)
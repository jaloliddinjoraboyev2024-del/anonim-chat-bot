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
CHANNELS = ["@imloviyku"] 
DB_NAME = 'imperial_v30.db'

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- DATABASE ---
def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=15)

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                          (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, 
                          link_token TEXT, join_date DATETIME, ban_until DATETIME)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER)')
        conn.commit()

def check_sub(uid):
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, uid).status
            if status in ['left', 'kicked']: return False
        except: continue
    return True

def is_banned(uid):
    with get_db_connection() as conn:
        res = conn.execute('SELECT ban_until FROM users WHERE id = ?', (uid,)).fetchone()
        if res and res[0]:
            ban_time = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() < ban_time: return ban_time
    return False

# --- START ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.chat.id
    if is_banned(uid):
        bot.send_message(uid, "🚫 Siz botdan 10 minutga chetlatilgansiz.")
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
        else:
            conn.execute('UPDATE users SET username = ?, full_name = ? WHERE id = ?', (uname, full_name, uid))
        conn.commit()
    
    if not check_sub(uid):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Kanalga a'zo bo'lish ➕", url=f"https://t.me/{CHANNELS[0][1:]}"))
        bot.send_message(uid, f"👋 <b>Assalomu alaykum!</b>\nBotdan foydalanish uchun kanalga a'zo bo'ling.", reply_markup=kb)
        return

    args = message.text.split()
    if len(args) > 1:
        token_arg = args[1]
        with get_db_connection() as conn:
            target = conn.execute('SELECT id FROM users WHERE link_token = ?', (token_arg,)).fetchone()
        
        if target and target[0] != uid:
            with get_db_connection() as conn:
                conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target[0]))
                conn.commit()
            bot.send_message(uid, "✨ <b>Siz anonim suhbatga ulandingiz!</b>\n\nMarhamat, xabaringizni yozing. 🔥", 
                             reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))
            return

    welcome_text = (
        f"🌟 <b>Salom, {first_name}! Anonim olamiga xush kelibsiz!</b>\n\n"
        f"1️⃣ O'z shaxsingizni yashirgan holda gaplashishingiz;\n"
        f"2️⃣ Siz haqingizda nima deb o'ylashlarini bilib olishingiz mumkin! 🔥\n\n"
        f"👇 <b>Boshlash uchun tugmalardan foydalaning:</b>"
    )
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
    if uid == ADMIN_ID: m.add("⚙️ Admin Panel")
    bot.send_message(uid, welcome_text, reply_markup=m)

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    
    if call.data == "refresh_link":
        new_token = secrets.token_hex(4)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET link_token = ? WHERE id = ?', (new_token, uid))
            conn.commit()
        bot.answer_callback_query(call.id, "Havola yangilandi! ✅")
        # Yangi havolani yuborish
        link = f"https://t.me/{bot.get_me().username}?start={new_token}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🚀 Do'stlarga ulashish", url=f"https://t.me/share/url?url={link}"))
        kb.add(types.InlineKeyboardButton("🔄 Havolani yangilash", callback_data="refresh_link"))
        bot.edit_message_text(f"🔗 <b>Yangi havolangiz:</b>\n\n{link}\n\nEski havolangiz endi ishlamaydi! ⚠️", uid, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("reply_"):
        target_id = int(call.data.split("_")[1])
        with get_db_connection() as conn:
            conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target_id))
            conn.commit()
        bot.send_message(uid, "✨ <b>Marhamat, yozing:</b>", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))

    elif call.data.startswith("report_"):
        rep_id = call.data.split("_")[1]
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_acc_{rep_id}_{uid}"),
            types.InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_rej_{uid}")
        )
        bot.send_message(ADMIN_ID, f"🚩 <b>SHIKOYAT:</b>\nID: <code>{rep_id}</code>\nShikoyatchi: <code>{uid}</code>", reply_markup=kb)
        bot.answer_callback_query(call.id, "Adminga yuborildi.")

    elif call.data.startswith("adm_acc_"):
        bad_id, reporter = call.data.split("_")[2], call.data.split("_")[3]
        ban_v = datetime.now() + timedelta(minutes=10)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET ban_until = ? WHERE id = ?', (ban_v, bad_id))
            conn.commit()
        bot.send_message(bad_id, "⚠️ <b>Sizning ustingizdan shikoyat tushdi!</b>\nAdmin tasdiqlovi bo'yicha siz 10 minutga botdan foydalana olmaysiz.")
        bot.send_message(reporter, "✅ Shikoyatingiz tasdiqlandi, aybdor 10 minutga bloklandi.")
        bot.edit_message_text(f"✅ ID {bad_id} bloklandi.", ADMIN_ID, call.message.message_id)

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    if not check_sub(uid) or is_banned(uid): return

    if message.text == "💎 Shaxsiy havola":
        with get_db_connection() as conn:
            token = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()[0]
        link = f"https://t.me/{bot.get_me().username}?start={token}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🚀 Do'stlarga ulashish", url=f"https://t.me/share/url?url={link}"))
        kb.add(types.InlineKeyboardButton("🔄 Havolani yangilash", callback_data="refresh_link"))
        bot.send_message(uid, f"🔗 <b>Sizning havolangiz:</b>\n\n{link}\n\nMenga anonim xabar yuboring! 😉", reply_markup=kb)
        return

    elif message.text == "🛑 Suhbatni yakunlash":
        with get_db_connection() as conn:
            conn.execute('DELETE FROM active_chats WHERE user_id = ? OR partner_id = ?', (uid, uid))
            conn.commit()
        bot.send_message(uid, "🔴 Suhbat yakunlandi.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info"))
        return

    # Xabar yo'naltirish qismi (Oldingi kod bilan bir xil)
    with get_db_connection() as conn:
        res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()
    if res:
        p_id = res[0]
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✍️ Javob berish", callback_data=f"reply_{uid}"),
            types.InlineKeyboardButton("⚠️ Shikoyat qilish", callback_data=f"report_{uid}")
        )
        try:
            bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
            bot.send_message(uid, "✅ Yuborildi!")
            # Admin log...
            bot.send_message(ADMIN_ID, f"📄 <b>LOG:</b>\nKimdan: {uid}\nKimga: {p_id}")
            bot.copy_message(ADMIN_ID, uid, message.message_id)
        except: bot.send_message(uid, "❌ Xatolik.")

if __name__ == '__main__':
    init_db()
    bot.infinity_polling(skip_pending=True)
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
                          ban_until DATETIME, link_token TEXT, join_date DATETIME)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER)')
        conn.commit()

def check_sub(uid):
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, uid).status
            if status in ['left', 'kicked']: return False
        except: continue
    return True

# --- START ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.chat.id
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
            token = user_data[0]
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
            bot.send_message(uid, "✨ <b>Siz anonim suhbatga ulandingiz!</b>\nXabaringizni yozing.", 
                             reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))
            return

    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
    if uid == ADMIN_ID: m.add("⚙️ Admin Panel")
    bot.send_message(uid, f"🌟 <b>Salom, {first_name}!</b>\nBotga xush kelibsiz!", reply_markup=m)

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    if call.data == "admin_stats" and uid == ADMIN_ID:
        with get_db_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        bot.send_message(ADMIN_ID, f"📊 <b>Statistika:</b>\n\nJami foydalanuvchilar: {total}")

    elif call.data == "admin_ad" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
        msg = bot.send_message(ADMIN_ID, "📝 <b>Reklama xabarini yuboring:</b>", reply_markup=kb)
        bot.register_next_step_handler(msg, broadcast_ad)

    elif call.data == "cancel_ad" and uid == ADMIN_ID:
        bot.clear_step_handler_by_chat_id(chat_id=ADMIN_ID)
        bot.edit_message_text("❌ <b>Reklama bekor qilindi.</b>", ADMIN_ID, call.message.message_id)

# --- REKLAMA ---
def broadcast_ad(message):
    if message.text in ["⚙️ Admin Panel", "/start", "🛑 Suhbatni yakunlash"]: return
    with get_db_connection() as conn:
        users = conn.execute('SELECT id FROM users').fetchall()
    bot.send_message(ADMIN_ID, "🚀 Yuborilmoqda...")
    count = 0
    for u in users:
        try:
            bot.copy_message(u[0], ADMIN_ID, message.message_id)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ {count} ta odamga yuborildi.")

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    if not check_sub(uid): return

    # 1. TUGMALAR (Sherikka yo'naltirilmaydi)
    if message.text == "💎 Shaxsiy havola":
        with get_db_connection() as conn:
            token = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()[0]
        link = f"https://t.me/{bot.get_me().username}?start={token}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("♻️ Ulashish", url=f"https://t.me/share/url?url={link}"))
        bot.send_message(uid, f"🔗 <b>Sizning havolangiz:</b>\n\n{link}", reply_markup=kb)
        return

    elif message.text == "👤 Profilim":
        with get_db_connection() as conn:
            u = conn.execute('SELECT full_name, join_date FROM users WHERE id = ?', (uid,)).fetchone()
        bot.send_message(uid, f"👤 <b>Ism:</b> {u[0]}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Sana:</b> {u[1][:10]}")
        return

    elif message.text == "ℹ️ Info":
        bot.send_message(uid, "ℹ️ <b>Bu bot orqali anonim xabarlar yuborishingiz mumkin.</b>\nShaxsingiz sir saqlanadi!")
        return

    elif message.text == "🛑 Suhbatni yakunlash":
        with get_db_connection() as conn:
            conn.execute('DELETE FROM active_chats WHERE user_id = ? OR partner_id = ?', (uid, uid))
            conn.commit()
        m = types.ReplyKeyboardMarkup(resize_keyboard=True).add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
        if uid == ADMIN_ID: m.add("⚙️ Admin Panel")
        bot.send_message(uid, "🔴 Suhbat yakunlandi.", reply_markup=m)
        return

    elif message.text == "⚙️ Admin Panel" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
                                              types.InlineKeyboardButton("📢 Reklama", callback_data="admin_ad"))
        bot.send_message(uid, "👑 <b>Admin Paneli</b>", reply_markup=kb)
        return

    # 2. XABAR YO'NALTIRISH
    with get_db_connection() as conn:
        res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()
    
    if res:
        p_id = res[0]
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✍️ Javob berish", url=f"https://t.me/{bot.get_me().username}?start={uid}"))
        try:
            bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
            bot.send_message(uid, "✅ Yuborildi!")
            
            # --- LOG ---
            with get_db_connection() as conn:
                p_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (p_id,)).fetchone()
            s_name = message.from_user.full_name
            s_user = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
            
            admin_report = (
                f"📑 <b>XABAR NAZORATI</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 <b>Yuboruvchi:</b> {s_name}\n"
                f"🎭 <b>User:</b> {s_user}\n"
                f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                f"-------------------------------\n"
                f"🎯 <b>Qabul qiluvchi:</b> {p_info[0]}\n"
                f"🎭 <b>User:</b> {p_info[1]}\n"
                f"🆔 <b>ID:</b> <code>{p_id}</code>\n"
                f"━━━━━━━━━━━━━━━"
            )
            bot.send_message(ADMIN_ID, admin_report)
            bot.copy_message(ADMIN_ID, uid, message.message_id)
        except: bot.send_message(uid, "❌ Xatolik.")

if __name__ == '__main__':
    init_db()
    bot.infinity_polling(skip_pending=True)
import telebot
from telebot import types
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
import os
import secrets
from dotenv import load_dotenv

# --- KONFIGURATSIYA ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7642176910 
CHANNELS = ["@imloviyku"] 
DB_NAME = 'imperial_v30.db'

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# --- DATABASE FUNKSIYALARI ---
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

def is_banned(uid):
    with get_db_connection() as conn:
        user = conn.execute('SELECT ban_until FROM users WHERE id = ?', (uid,)).fetchone()
        if user and user[0]:
            try:
                ban_time = datetime.strptime(user[0], '%Y-%m-%d %H:%M:%S.%f')
                if datetime.now() < ban_time: return ban_time
            except: pass
    return None

# --- START HANDLER ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.chat.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    uname = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
    
    with get_db_connection() as conn:
        user_data = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()
        if not user_data:
            token = secrets.token_hex(4)
            conn.execute('''INSERT INTO users (id, username, full_name, link_token, join_date) 
                            VALUES (?, ?, ?, ?, ?)''', (uid, uname, full_name, token, datetime.now()))
        else:
            token = user_data[0]
            conn.execute('UPDATE users SET username = ?, full_name = ? WHERE id = ?', (uname, full_name, uid))
        conn.commit()
    
    if not check_sub(uid):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Kanalga a'zo bo'lish ➕", url=f"https://t.me/{CHANNELS[0][1:]}"))
        bot.send_message(uid, f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\nBotdan foydalanish uchun kanalga a'zo bo'ling.", reply_markup=kb)
        return

    args = message.text.split()
    if len(args) > 1:
        token_arg = args[1]
        with get_db_connection() as conn:
            target = conn.execute('SELECT id FROM users WHERE link_token = ?', (token_arg,)).fetchone()
        
        if target:
            target_id = target[0]
            if target_id != uid:
                with get_db_connection() as conn:
                    conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target_id))
                    conn.commit()
                bot.send_message(uid, "✨ <b>Siz anonim suhbatga ulandingiz!</b>\nXabaringizni yozing.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash"))
                return
        else:
            bot.send_message(uid, "⚠️ <b>Bu havola eskirgan!</b>")

    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
    if uid == ADMIN_ID: m.add("⚙️ Admin Panel")
    bot.send_message(uid, f"🌟 <b>Salom, {first_name}!</b> Botga xush kelibsiz!", reply_markup=m)

# --- CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data.split(':')
    
    if data[0] == "refresh_link":
        new_token = secrets.token_hex(4)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET link_token = ? WHERE id = ?', (new_token, uid))
            conn.commit()
        bot.answer_callback_query(call.id, "Havolangiz yangilandi! ✅", show_alert=True)
        link = f"https://t.me/{bot.get_me().username}?start={new_token}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("♻️ Ulashish", url=f"https://t.me/share/url?url={link}"))
        kb.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_link"))
        bot.edit_message_text(f"🔗 <b>Yangi havolangiz:</b>\n\n{link}", uid, call.message.message_id, reply_markup=kb)

    elif data[0] == "admin_stats":
        with get_db_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            today = datetime.now() - timedelta(days=1)
            new_users = conn.execute('SELECT COUNT(*) FROM users WHERE join_date > ?', (today,)).fetchone()[0]
        growth = (new_users / total * 100) if total > 0 else 0
        bot.send_message(ADMIN_ID, f"📊 <b>Bot Statistikasi</b>\n\n👥 Jami: {total}\n📈 Bugun: +{new_users} ({growth:.1f}%)\n📉 Pasayish: 0% (Stabil)")

    elif data[0] == "admin_ad":
        msg = bot.send_message(ADMIN_ID, "📝 Reklama xabarini yuboring:")
        bot.register_next_step_handler(msg, broadcast_ad)

# --- REKLAMA FUNKSIYASI ---
def broadcast_ad(message):
    with get_db_connection() as conn:
        users = conn.execute('SELECT id FROM users').fetchall()
    count = 0
    for u in users:
        try:
            bot.copy_message(u[0], ADMIN_ID, message.message_id)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ {count} ta foydalanuvchiga yuborildi.")

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    if is_banned(uid): return
    if not check_sub(uid): return

    # --- TUGMALAR TEKSHIRUVI (Sherikka ketmasligi uchun) ---
    if message.text == "💎 Shaxsiy havola":
        with get_db_connection() as conn:
            token = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()[0]
        link = f"https://t.me/{bot.get_me().username}?start={token}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("♻️ Ulashish", url=f"https://t.me/share/url?url={link}"))
        kb.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_link"))
        bot.send_message(uid, f"🔗 <b>Sizning havolangiz:</b>\n\n{link}", reply_markup=kb)
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
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"), types.InlineKeyboardButton("📢 Reklama", callback_data="admin_ad"))
        bot.send_message(uid, "👑 Admin Paneli:", reply_markup=kb)
        return

    # --- XABAR YO'NALTIRISH VA SKRINSHOTDAGI LOG ---
    with get_db_connection() as conn:
        res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()
    
    if res:
        p_id = res[0]
        with get_db_connection() as conn:
            p_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (p_id,)).fetchone()
        
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✍️ Javob berish", url=f"https://t.me/{bot.get_me().username}?start={secrets.token_hex(2)}"))
        
        try:
            bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
            bot.send_message(uid, "✅ Yuborildi!")
            
            # --- ADMINGA TO'LIQ LOG (Siz so'ragan format) ---
            s_name = message.from_user.full_name
            s_user = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
            p_name = p_info[0]
            p_user = p_info[1]
            
            admin_report = (
                f"📄 <b>XABAR NAZORATI</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"👤 <b>Yuboruvchi:</b> {s_name}\n"
                f"🎭 <b>User:</b> {s_user}\n"
                f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                f"-------------------------------\n"
                f"🎯 <b>Qabul qiluvchi:</b> {p_name}\n"
                f"🎭 <b>User:</b> {p_user}\n"
                f"🆔 <b>ID:</b> <code>{p_id}</code>\n"
                f"━━━━━━━━━━━━━━━"
            )
            bot.send_message(ADMIN_ID, admin_report)
            bot.copy_message(ADMIN_ID, uid, message.message_id)
        except: bot.send_message(uid, "❌ Xabar yetkazilmadi.")
    else:
        if message.text and message.text not in ["👤 Profilim", "ℹ️ Info"]:
            bot.send_message(uid, "🧐 Kimga yozmoqchisiz? Havolaga bosing!")

if __name__ == '__main__':
    init_db()
    bot.infinity_polling(skip_pending=True)
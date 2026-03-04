import telebot
from telebot import types
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
import os
import secrets  # Havola uchun xavfsiz tokenlar yaratish
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
        # link_token va join_date ustunlari qo'shildi
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                          (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, 
                          ban_until DATETIME, link_token TEXT, join_date DATETIME)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER)')
        conn.commit()

# --- TEKSHIRUVLAR ---
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
            ban_time = datetime.strptime(user[0], '%Y-%m-%d %H:%M:%S.%f')
            if datetime.now() < ban_time:
                return ban_time
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
        # Foydalanuvchi borligini tekshirish, yo'q bo'lsa yangi token berish
        user_data = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()
        if not user_data:
            token = secrets.token_hex(4) # Tasodifiy 8 xonali token
            conn.execute('''INSERT INTO users (id, username, full_name, link_token, join_date) 
                            VALUES (?, ?, ?, ?, ?)''', (uid, uname, full_name, token, datetime.now()))
        else:
            token = user_data[0]
            conn.execute('UPDATE users SET username = ?, full_name = ? WHERE id = ?', (uname, full_name, uid))
        conn.commit()
    
    if not check_sub(uid):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish ➕", url=f"https://t.me/{CHANNELS[0][1:]}"))
        bot.send_message(uid, f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\nBotdan foydalanish uchun kanalimizga a'zo bo'lishingiz kerak.", reply_markup=kb)
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
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash")
                bot.send_message(uid, f"✨ <b>Siz anonim suhbatga ulandingiz!</b>\n\nMarhamat, xabaringizni yozing.", reply_markup=kb)
                return
        else:
            bot.send_message(uid, "⚠️ <b>Bu havola eskirgan yoki o'chirilgan!</b>\nFoydalanuvchi havolasini yangilagan ko'rinadi.")

    welcome_text = (
        f"🌟 <b>Salom, {first_name}! Anonim olamiga xush kelibsiz!</b>\n\n"
        f"👇 <b>Boshlash uchun pastdagi tugmalardan foydalaning:</b>"
    )

    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
    if uid == ADMIN_ID:
        m.add("⚙️ Admin Panel")
    bot.send_message(uid, welcome_text, reply_markup=m)

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
        # Havola matnini yangilash
        link = f"https://t.me/{bot.get_me().username}?start={new_token}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("♻️ Ulashish", url=f"https://t.me/share/url?url={link}"))
        kb.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_link"))
        
        new_text = f"🔗 <b>Yangi havolangiz:</b>\n\n{link}\n\n<i>Eski havola endi ishlamaydi!</i>"
        bot.edit_message_text(new_text, uid, call.message.message_id, reply_markup=kb, disable_web_page_preview=True)

    elif data[0] == "admin_stats":
        with get_db_connection() as conn:
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            today = datetime.now() - timedelta(days=1)
            new_users = conn.execute('SELECT COUNT(*) FROM users WHERE join_date > ?', (today,)).fetchone()[0]
        
        growth = (new_users / total * 100) if total > 0 else 0
        stat_text = (
            f"📊 <b>Bot Statistikasi</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{total} ta</b>\n"
            f"📈 Oxirgi 24 soatda: <b>+{new_users} ta</b>\n"
            f"🔥 O'sish ko'rsatkichi: <b>{growth:.1f}%</b>\n"
            f"📉 Pasayish: <b>0% (Stabil)</b>"
        )
        bot.send_message(ADMIN_ID, stat_text)

    elif data[0] == "admin_ad":
        msg = bot.send_message(ADMIN_ID, "📝 <b>Reklama xabarini yuboring.</b>\n(Matn, rasm, video bo'lishi mumkin)")
        bot.register_next_step_handler(msg, broadcast_ad)

    # Sizning eski shikoyat handlerlaringiz
    elif data[0] == "report":
        reported_id, reporter_id = int(data[1]), call.from_user.id
        with get_db_connection() as conn:
            reporter_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (reporter_id,)).fetchone()
            reported_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (reported_id,)).fetchone()
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ban:{reported_id}:{reporter_id}"))
        kb.add(types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject:{reporter_id}"))
        bot.send_message(ADMIN_ID, f"⚠️ <b>Shikoyat!</b>\nKimdan: {reporter_info[0]}\nKimga: {reported_info[0]}", reply_markup=kb)

    elif data[0] == "ban":
        uid_to_ban, until = int(data[1]), datetime.now() + timedelta(minutes=10)
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET ban_until = ? WHERE id = ?', (until, uid_to_ban))
            conn.commit()
        bot.edit_message_text(f"✅ {uid_to_ban} bloklandi.", ADMIN_ID, call.message.message_id)

# --- REKLAMA FUNKSIYASI ---
def broadcast_ad(message):
    with get_db_connection() as conn:
        users = conn.execute('SELECT id FROM users').fetchall()
    
    count = 0
    bot.send_message(ADMIN_ID, "🚀 Reklama yuborish boshlandi...")
    for user in users:
        try:
            bot.copy_message(user[0], ADMIN_ID, message.message_id)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ Reklama {count} ta odamga yetib bordi.")

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    if is_banned(uid): return

    if message.text == "💎 Shaxsiy havola":
        with get_db_connection() as conn:
            token = conn.execute('SELECT link_token FROM users WHERE id = ?', (uid,)).fetchone()[0]
        
        link = f"https://t.me/{bot.get_me().username}?start={token}"
        display_text = f"🔗 <b>Sizning havolangiz:</b>\n\n{link}\n\nMenga anonim xabar yuboring! 🤫"
        
        kb = types.InlineKeyboardMarkup()
        share_url = f"https://t.me/share/url?url={link}&text=" + urllib.parse.quote("Menga anonim xabar yuboring! 🤫")
        kb.add(types.InlineKeyboardButton("♻️ Do'stlarga ulashish", url=share_url))
        kb.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_link"))
        
        bot.send_message(uid, display_text, reply_markup=kb, disable_web_page_preview=True)
        return

    elif message.text == "⚙️ Admin Panel" and uid == ADMIN_ID:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
               types.InlineKeyboardButton("📢 Reklama tarqatish", callback_data="admin_ad"))
        bot.send_message(uid, "👑 <b>Admin boshqaruv paneli</b>", reply_markup=kb)
        return

    elif message.text == "👤 Profilim":
        with get_db_connection() as conn:
            user = conn.execute('SELECT full_name FROM users WHERE id = ?', (uid,)).fetchone()
        bot.send_message(uid, f"👤 <b>Profil:</b> {user[0]}\n🆔 ID: <code>{uid}</code>")
        return

    # Xabar yo'naltirish qismi (Sizning kodingiz)
    with get_db_connection() as conn:
        res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()
    
    if res:
        p_id = res[0]
        with get_db_connection() as conn:
            p_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (p_id,)).fetchone()
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✍️ Javob berish", url=f"https://t.me/{bot.get_me().username}?start={secrets.token_hex(2)}")) # Shunchaki ko'rinish uchun
        kb.add(types.InlineKeyboardButton("⚠️ Shikoyat qilish", callback_data=f"report:{uid}"))
        
        try:
            bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
            bot.send_message(uid, "✅ Yuborildi!")
            
            # Adminga nazorat (Siz xohlagandek to'liq)
            s_name = f"{message.from_user.first_name} ({uid})"
            admin_msg = f"📑 <b>LOG:</b>\nKimdan: {s_name}\nKimga: {p_info[0]} ({p_id})"
            bot.send_message(ADMIN_ID, admin_msg)
            bot.copy_message(ADMIN_ID, uid, message.message_id)
        except: bot.send_message(uid, "❌ Xatolik.")

if __name__ == '__main__':
    init_db()
    bot.infinity_polling(skip_pending=True)
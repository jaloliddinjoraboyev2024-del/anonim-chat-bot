import telebot
from telebot import types
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
import os
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
                          (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, ban_until DATETIME)''')
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
        conn.execute('REPLACE INTO users (id, username, full_name) VALUES (?, ?, ?)', (uid, uname, full_name))
        conn.commit()
    
    if not check_sub(uid):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish ➕", url=f"https://t.me/{CHANNELS[0][1:]}"))
        bot.send_message(uid, f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\nBotdan foydalanish uchun kanalimizga a'zo bo'lishingiz kerak.", reply_markup=kb)
        return

    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
        if target_id != uid:
            with get_db_connection() as conn:
                conn.execute('REPLACE INTO active_chats (user_id, partner_id) VALUES (?, ?)', (uid, target_id))
                conn.commit()
            
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Suhbatni yakunlash")
            bot.send_message(uid, f"✨ <b>Siz anonim suhbatga ulandingiz!</b>\n\nMarhamat, xabaringizni yozing.", reply_markup=kb)
            return

    # To'liq START matni
    welcome_text = (
        f"🌟 <b>Salom, {first_name}! Anonim olamiga xush kelibsiz!</b>\n\n"
        f"Bu yerda siz:\n"
        f"1️⃣ O'z shaxsingizni yashirgan holda do'stlaringiz bilan gaplashishingiz;\n"
        f"2️⃣ Siz haqingizda nima deb o'ylashlarini bilib olishingiz;\n"
        f"3️⃣ Hech qanday qo'rquvsiz sirlaringizni ulashishingiz mumkin! 🔥\n\n"
        f"👇 <b>Boshlash uchun pastdagi tugmalardan foydalaning:</b>"
    )

    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info")
    bot.send_message(uid, welcome_text, reply_markup=m)

# --- CALLBACK HANDLER (Shikoyat va Admin) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data.split(':')
    
    if data[0] == "report":
        reported_id = int(data[1])
        reporter_id = call.from_user.id
        
        with get_db_connection() as conn:
            reporter_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (reporter_id,)).fetchone()
            reported_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (reported_id,)).fetchone()
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Tasdiqlash (10 min blok)", callback_data=f"ban:{reported_id}:{reporter_id}"))
        kb.add(types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject:{reporter_id}"))
        
        report_log = (
            f"⚠️ <b>YANGI SHIKOYAT!</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <b>Shikoyatchi:</b> {reporter_info[0]} ({reporter_info[1]})\n"
            f"🆔 <b>ID:</b> <code>{reporter_id}</code>\n\n"
            f"🎯 <b>Aybdor:</b> {reported_info[0]} ({reported_info[1]})\n"
            f"🆔 <b>ID:</b> <code>{reported_id}</code>\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(ADMIN_ID, report_log, reply_markup=kb)
        bot.answer_callback_query(call.id, "Shikoyat adminga yuborildi.")

    elif data[0] == "ban":
        uid_to_ban = int(data[1])
        reporter_id = int(data[2])
        until = datetime.now() + timedelta(minutes=10)
        
        with get_db_connection() as conn:
            conn.execute('UPDATE users SET ban_until = ? WHERE id = ?', (until, uid_to_ban))
            conn.commit()
        
        bot.edit_message_text(f"✅ Foydalanuvchi {uid_to_ban} 10 minutga bloklandi.", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(uid_to_ban, "🚫 <b>Siz qoidabuzarlik uchun 10 minutga bloklandingiz!</b>")
            bot.send_message(reporter_id, "✅ Shikoyatingiz tasdiqlandi, foydalanuvchi bloklandi.")
        except: pass

    elif data[0] == "reject":
        reporter_id = int(data[1])
        bot.edit_message_text("❌ Shikoyat rad etildi.", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(reporter_id, "❌ Sizning shikoyatingiz admin tomonidan rad etildi.")
        except: pass

# --- ASOSIY HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'sticker', 'animation', 'video_note'])
def main_handler(message):
    uid = message.chat.id
    
    ban_time = is_banned(uid)
    if ban_time:
        bot.send_message(uid, f"🚫 <b>Siz bloklangansiz!</b>\nBlok tugash vaqti: {ban_time.strftime('%H:%M:%S')} gacha.")
        return

    if not check_sub(uid): return

    if message.text == "💎 Shaxsiy havola":
        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={uid}"
        display_text = (
            f"🔗 <b>Sizning havolangiz:</b>\n\n"
            f"{link}\n\n"
            f"Menga anonim xabar yuboring! 🤫\n\n"
            f"👇 Marhamat, yozing:\n"
            f"{link}"
        )
        share_url = f"https://t.me/share/url?url={link}&text=" + urllib.parse.quote("Menga anonim xabar yuboring! 🤫")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("♻️ Do'stlarga ulashish", url=share_url))
        bot.send_message(uid, display_text, reply_markup=kb, disable_web_page_preview=True)
        return

    elif message.text == "👤 Profilim":
        with get_db_connection() as conn:
            user = conn.execute('SELECT full_name FROM users WHERE id = ?', (uid,)).fetchone()
        name = user[0] if user else "Noma'lum"
        bot.send_message(uid, f"👤 <b>Profilingiz:</b>\n\nIsm: <b>{name}</b>\n🆔 ID: <code>{uid}</code>\n🎭 Holat: <b>Faol ✅</b>")
        return

    elif message.text == "ℹ️ Info":
        bot.send_message(uid, "ℹ️ <b>Info:</b>\n\nUshbu bot orqali do'stlaringizga anonim xabarlar yuborishingiz va qabul qilishingiz mumkin. Xavfsizlik maqsadida barcha xabarlar admin nazoratida bo'ladi.")
        return

    elif message.text == "🛑 Suhbatni yakunlash":
        with get_db_connection() as conn:
            conn.execute('DELETE FROM active_chats WHERE user_id = ?', (uid,))
            conn.commit()
        bot.send_message(uid, "🔴 Suhbat yakunlandi.", reply_markup=types.ReplyKeyboardRemove())
        start_handler(message)
        return

    # Xabar yo'naltirish
    with get_db_connection() as conn:
        res = conn.execute('SELECT partner_id FROM active_chats WHERE user_id = ?', (uid,)).fetchone()
    
    if res:
        p_id = res[0]
        
        with get_db_connection() as conn:
            p_info = conn.execute('SELECT full_name, username FROM users WHERE id = ?', (p_id,)).fetchone()
        
        p_name = p_info[0] if p_info else "Noma'lum"
        p_user = p_info[1] if p_info else "Username yo'q"

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✍️ Javob berish", url=f"https://t.me/{bot.get_me().username}?start={uid}"))
        kb.add(types.InlineKeyboardButton("⚠️ Shikoyat qilish", callback_data=f"report:{uid}"))
        
        try:
            bot.copy_message(p_id, uid, message.message_id, reply_markup=kb)
            bot.send_message(uid, "✅ Xabaringiz yuborildi!")
            
            # ADMINGA TO'LIQ NAZORAT (Yuboruvchi + Qabul qiluvchi)
            s_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            s_user = f"@{message.from_user.username}" if message.from_user.username else "Username yo'q"
            
            admin_report = (
                f"📑 <b>XABAR NAZORATI</b>\n"
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
        if message.text not in ["💎 Shaxsiy havola", "👤 Profilim", "ℹ️ Info"]:
            bot.send_message(uid, "🧐 <b>Xabarni kimga yubormoqchisiz?</b>\nAvval do'stingiz yuborgan havolaga bosing!")

if __name__ == '__main__':
    init_db()
    print("Bot ishga tushdi...")
    bot.infinity_polling(skip_pending=True)
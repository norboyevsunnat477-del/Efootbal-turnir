import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# ================= KO'RSATMALAR =================
# 1. BOT_TOKEN: BotFather bergan tokenni kiriting
# 2. ADMIN_ID: Telegram ID raqamingizni kiriting (@userinfobot orqali bilsangiz bo'ladi)
# 3. CHANNEL_USERNAME: Majburiy obuna kanali username'i (@ belgisi bilan)
# ================================================

BOT_TOKEN = "8802613886:AAF9SvRntPSB8b1GXaNrWFy1zGJiBa7_NP8"
ADMIN_ID = 5244022908  
CHANNEL_USERNAME = "@EFMOBILEUZ"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE TIZIMI ---
def init_db():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            daily_games INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            result TEXT,
            points_awarded INTEGER,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FSM STATES ---
class MatchSubmission(StatesGroup):
    waiting_for_photo = State()
    waiting_for_result = State()

# --- MAJBURIY OBUNA TEKSHIRISH ---
async def check_sub(user_id: int) -> bool:
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@kanalingiz_username":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

# --- START HANDLER ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    is_sub = await check_sub(message.from_user.id)
    if not is_sub:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")]
        ])
        await message.answer("⚠️ Botdan foydalanish uchun rasmiy kanalimizga a'zo bo'ling:", reply_markup=kb)
        return

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
                   (message.from_user.id, message.from_user.username or "Foydalanuvchi"))
    conn.commit()
    conn.close()
    
    await message.answer(
        "👋 **Turnir botiga xush kelibsiz!**\n\n"
        "🎮 **Buyruqlar:**\n"
        "📸 /submit - O'yin skrinshotini yuborish (Kunlik limit: 5 ta)\n"
        "🏆 /leaderboard - TOP 16 o'yinchilar ro'yxati\n"
        "⚽ /liga - Liga Mini App'ini ochish",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Rahmat! A'zolik tasdiqlandi. /start tugmasini bosing.")
    else:
        await call.answer("❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- LEADERBOARD ---
@dp.message(Command("leaderboard"))
async def show_leaderboard(message: types.Message):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 16")
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await message.answer("🏆 Hozircha leaderboard bo'sh.")
        return

    text = "🏆 **TOP 16 LEADERBOARD (Saralash)**\n\n"
    for idx, (username, points) in enumerate(top_users, start=1):
        text += f"{idx}. @{username} — **{points}** ochko\n"
    
    await message.answer(text, parse_mode="Markdown")

# --- SKRINSHOT VA NATIJA YUBORISH ---
@dp.message(Command("submit"))
async def start_submit(message: types.Message, state: FSMContext):
    if not await check_sub(message.from_user.id):
        await message.answer("⚠️ Avval kanalga a'zo bo'ling! /start")
        return

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_games FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()

    if user and user[0] >= 5:
        await message.answer("⛔ Bugungi 5 ta o'yin limitidan foydalanib bo'ldingiz! Ertaga yana urinib ko'ring.")
        return

    await state.set_state(MatchSubmission.waiting_for_photo)
    await message.answer("📸 O'yin natijasi ko'ringan skrinshotni yuboring:")

@dp.message(MatchSubmission.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 G'alaba (+3 ochko)", callback_data="res_win")],
        [InlineKeyboardButton(text="🤝 Durrang (+1 ochko)", callback_data="res_draw")],
        [InlineKeyboardButton(text="❌ Mag'lubiyat (0 ochko)", callback_data="res_loss")]
    ])
    await state.set_state(MatchSubmission.waiting_for_result)
    await message.answer("⚡ O'yin natijangizni tanlang:", reply_markup=kb)

@dp.callback_query(MatchSubmission.waiting_for_result, F.data.startswith("res_"))
async def process_result(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    res_type = call.data.split("_")[1]
    
    points_map = {"win": 3, "draw": 1, "loss": 0}
    pts = points_map[res_type]

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO matches (user_id, result, points_awarded) VALUES (?, ?, ?)", 
                   (call.from_user.id, res_type, pts))
    match_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Admin panelga yuborish
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{match_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{match_id}")
        ]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=data['photo_id'],
        caption=(
            f"📩 **Yangi Ariza #{match_id}**\n"
            f"👤 O'yinchi: @{call.from_user.username or call.from_user.id}\n"
            f"📊 Natija: **{res_type.upper()}** ({pts} ochko)"
        ),
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )
    
    await call.message.edit_text("⏳ Arizangiz adminga yuborildi. Tekshirilgandan so'ng ochko beriladi.")
    await state.clear()

# --- ADMIN TASDIQLASH VA SHIKOYAT/ATKAZ TIZIMI ---
@dp.callback_query(F.data.startswith("approve_"))
async def approve_match(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Siz admin emassiz!", show_alert=True)
        return

    match_id = int(call.data.split("_")[1])
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, points_awarded, status FROM matches WHERE id = ?", (match_id,))
    match = cursor.fetchone()

    if match and match[2] == 'PENDING':
        u_id, pts, status = match
        cursor.execute("UPDATE matches SET status = 'APPROVED' WHERE id = ?", (match_id,))
        cursor.execute("UPDATE users SET points = points + ?, daily_games = daily_games + 1 WHERE user_id = ?", (pts, u_id))
        conn.commit()
        
        # Noto'g'ri berilgan bo'lsa qayta ayirib tashlash tugmasi
        edit_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Bekor qilish / Ochkoni ayirish", callback_data=f"reject_{match_id}")]
        ])
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n✅ **TASDIQLANDI (+ Ochko qo'shildi)**",
            reply_markup=edit_kb,
            parse_mode="Markdown"
        )
        await bot.send_message(u_id, f"🎉 Arizangiz tasdiqlandi! Hisobingizga +{pts} ochko qo'shildi.")
    conn.close()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_match(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ Siz admin emassiz!", show_alert=True)
        return

    match_id = int(call.data.split("_")[1])
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, points_awarded, status FROM matches WHERE id = ?", (match_id,))
    match = cursor.fetchone()

    if match:
        u_id, pts, status = match
        if status == 'APPROVED':
            # Ilgari tasdiqlangan bo'lsa — ochkoni qaytarib ayirib tashlaydi
            cursor.execute("UPDATE users SET points = MAX(0, points - ?), daily_games = MAX(0, daily_games - 1) WHERE user_id = ?", (pts, u_id))
        
        cursor.execute("UPDATE matches SET status = 'REJECTED' WHERE id = ?", (match_id,))
        conn.commit()
        
        await call.message.edit_caption(
            caption=call.message.caption + "\n\n❌ **RAD ETILDI / OCHKO AYIRILDI**",
            reply_markup=None,
            parse_mode="Markdown"
        )
        await bot.send_message(u_id, "⚠️ Natijangiz noto'g'ri deb topildi va berilgan ochko bekor qilindi.")
    conn.close()

# --- LIGA MINI APP ---
@dp.message(Command("liga"))
async def open_liga_app(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏆 LIGA JADVALINI OCHISH", 
            web_app=WebAppInfo(url="https://example.com/liga.html")
        )]
    ])
    await message.answer("⚽ Top 16 ligasi va turlar jadvalini ko'rish uchun quyidagi tugmani bosing:", reply_markup=kb)

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
                    

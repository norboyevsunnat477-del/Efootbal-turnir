import asyncio
import sqlite3
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8802613886:AAF9SvRntPSB8b1GXaNrWFy1zGJiBa7_NP8"
ADMIN_ID = 5244022908  
CHANNEL_USERNAME = "@EFMOBILEUZ"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DUMMY WEB SERVER (RENDER PORT CHECK UCHUN) ---
async def handle_health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- BAZANI SOZLASH ---
def init_db():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            daily_games INTEGER DEFAULT 0,
            in_league INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER,
            player2_id INTEGER,
            result TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class SubmitResult(StatesGroup):
    waiting_for_photo = State()
    waiting_for_score = State()

def main_keyboard():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎮 Raqib topish"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="📸 Natija yuborish"), KeyboardButton(text="⚽ Liga (Top 16)")]
    ], resize_keyboard=True)
    return kb

async def check_sub(user_id: int) -> bool:
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@kanalingiz_username":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not await check_sub(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
        ])
        await message.answer("⚠️ Botdan foydalanish uchun kanalimizga a'zo bo'ling:", reply_markup=kb)
        return

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
                   (message.from_user.id, message.from_user.username or "O'yinchi"))
    conn.commit()
    conn.close()

    await message.answer("⚡ **eFootball Turnir Botiga xush kelibsiz!**\n\n1-bosqich (Saralash) ketyapti. Kuniga 5 tagacha raqib topib o'ynashingiz mumkin.", reply_markup=main_keyboard())

@dp.message(F.text == "🎮 Raqib topish")
async def find_opponent(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT daily_games FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if user and user[0] >= 5:
        await message.answer("⛔ Bugungi 5 ta o'yin limitidan foydalanib bo'ldingiz! Ertaga yana urinib ko'ring.")
        conn.close()
        return

    cursor.execute("SELECT user_id FROM queue WHERE user_id != ? LIMIT 1", (user_id,))
    opponent = cursor.fetchone()

    if opponent:
        opp_id = opponent[0]
        cursor.execute("DELETE FROM queue WHERE user_id = ?", (opp_id,))
        cursor.execute("INSERT INTO matches (player1_id, player2_id) VALUES (?, ?)", (user_id, opp_id))
        match_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT username FROM users WHERE user_id = ?", (opp_id,))
        opp_name = cursor.fetchone()[0]
        
        await message.answer(f"🎉 **Raqib topildi!**\n👤 Raqibingiz: @{opp_name}\n\nO'yinni o'ynab, g'olib '📸 Natija yuborish' tugmasi orqali skrinshot yuborsin. O'yin ID: #{match_id}")
        await bot.send_message(opp_id, f"🎉 **Raqib topildi!**\n👤 Raqibingiz: @{message.from_user.username}\n\nO'yin ID: #{match_id}")
    else:
        cursor.execute("INSERT OR REPLACE INTO queue (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await message.answer("🔍 Raqib izlanmoqda... Boshqa o'yinchi 'Raqib topish'ni bossa, bot sizlarni biriktiradi.")
    
    conn.close()

@dp.message(F.text == "📸 Natija yuborish")
async def start_submit(message: types.Message, state: FSMContext):
    await state.set_state(SubmitResult.waiting_for_photo)
    await message.answer("📸 O'yin natijasi aks etgan skrinshotni yuboring:")

@dp.message(SubmitResult.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥇 Men yutdim (+3 ochko)", callback_data="win")],
        [InlineKeyboardButton(text="🤝 Durrang (+1 ochko)", callback_data="draw")],
        [InlineKeyboardButton(text="❌ Men yutqizdim (0 ochko)", callback_data="loss")]
    ])
    await state.set_state(SubmitResult.waiting_for_score)
    await message.answer("O'yinda erishgan natijangizni tanlang:", reply_markup=kb)

@dp.callback_query(SubmitResult.waiting_for_score)
async def process_score(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    res = call.data
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{call.from_user.id}_{res}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{call.from_user.id}_{res}")
        ]
    ])
    
    await bot.send_photo(
        ADMIN_ID, 
        data['photo_id'], 
        caption=f"📩 **Natija tekshiruvi:**\nO'yinchi: @{call.from_user.username}\nNatija: {res.upper()}",
        reply_markup=admin_kb
    )
    await call.message.edit_text("⏳ Natijangiz adminga yuborildi. Tekshirilgach ochko qo'shiladi.")
    await state.clear()

@dp.callback_query(F.data.startswith("app_"))
async def approve_match(call: types.CallbackQuery):
    _, user_id, res = call.data.split("_")
    user_id = int(user_id)
    pts = 3 if res == "win" else (1 if res == "draw" else 0)

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ?, daily_games = daily_games + 1 WHERE user_id = ?", (pts, user_id))
    conn.commit()
    conn.close()

    revert_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Noto'g'ri hisob (Ochkoni olib tashlash)", callback_data=f"rej_{user_id}_{res}")]
    ])

    await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ **Tasdiqlandi (+{pts} ochko berildi)**", reply_markup=revert_kb)
    await bot.send_message(user_id, f"🎉 Arizangiz tasdiqlandi! Hisobingizga +{pts} ochko qo'shildi.")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_match(call: types.CallbackQuery):
    _, user_id, res = call.data.split("_")
    user_id = int(user_id)
    pts = 3 if res == "win" else (1 if res == "draw" else 0)

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = MAX(0, points - ?), daily_games = MAX(0, daily_games - 1) WHERE user_id = ?", (pts, user_id))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ **RAD ETILDI (Ochko olib tashlandi)**", reply_markup=None)
    await bot.send_message(user_id, "⚠️ Natijangiz rad etildi va berilgan ochkolar olib tashlandi.")

@dp.message(F.text == "🏆 Leaderboard")
async def show_leaderboard(message: types.Message):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 16")
    users = cursor.fetchall()
    conn.close()

    text = "🏆 **SARALASH BOSQICHI — TOP 16**\n*(7-kun yakunida ushbu 16 kishi Ligaga o'tadi)*\n\n"
    for idx, (username, points) in enumerate(users, start=1):
        text += f"{idx}. @{username} — {points} ochko\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "⚽ Liga (Top 16)")
async def show_league(message: types.Message):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users WHERE in_league = 1 ORDER BY points DESC")
    league_users = cursor.fetchall()
    conn.close()

    if not league_users:
        await message.answer("⚽ **2-Bosqich: Liga** hali boshlanmadi.\n\nSaralash bosqichining 7-kuni yakunlangach, Top 16 o'yinchi bu yerga qo'shiladi. Mukofot: **50 000 so'm** (8 kun, kuniga 2 tadan tur).")
    else:
        text = "🔥 **50 000 SO'MLIK LIGA JADVALI** 🔥\n\n"
        for idx, (username, points) in enumerate(league_users, start=1):
            text += f"{idx}. @{username} — {points} ochko\n"
        await message.answer(text)

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    

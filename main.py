import asyncio
import sqlite3
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8802613886:AAF9SvRntPSB8b1GXaNrWFy1zGJiBa7_NP8"
ADMIN_ID = 5244022908  
CHANNEL_USERNAME = "@efmobileuz"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN WEB SERVER ---
async def handle_health_check(request):
    return web.Response(text="Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            daily_games INTEGER DEFAULT 0,
            in_league INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    ''')
    
    # Ustunlar mavjudligini tekshirish (Bazani yangilash)
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'wins' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN wins INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN draws INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id INTEGER PRIMARY KEY,
            opponent_id INTEGER,
            match_id INTEGER
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

def main_keyboard():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎮 Raqib topish"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="⚽ Liga (Top 16)")]
    ], resize_keyboard=True)
    return kb

def match_inline_keyboard(match_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yutdim", callback_data=f"res_win_{match_id}"),
            InlineKeyboardButton(text="🤝 Durang", callback_data=f"res_draw_{match_id}")
        ],
        [
            InlineKeyboardButton(text="❌ O'yinni bekor qilish", callback_data=f"res_cancel_{match_id}")
        ]
    ])
    return kb

def get_active_opponent(user_id):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT opponent_id, match_id FROM active_chats WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res

async def check_sub(user_id: int) -> bool:
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@kanalingiz_username":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

# --- HANDLERS ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
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

# --- RAQIB TOPISH VA CHAT OCHISH ---
@dp.message(F.text == "🎮 Raqib topish")
async def find_opponent(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    if get_active_opponent(user_id):
        await message.answer("⚠️ Sizda hozirda faol o'yin mavjud! Avval o'yinni yakunlang yoki bekor qiling.")
        return

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
        
        cursor.execute("INSERT OR REPLACE INTO active_chats (user_id, opponent_id, match_id) VALUES (?, ?, ?)", (user_id, opp_id, match_id))
        cursor.execute("INSERT OR REPLACE INTO active_chats (user_id, opponent_id, match_id) VALUES (?, ?, ?)", (opp_id, user_id, match_id))
        conn.commit()

        text = (
            "✅ **Raqib topildi!** Endi u bilan shu chat orqali anonim yozishingiz mumkin.\n"
            "O'yin tugagach natijani belgilang:"
        )
        
        await message.answer(text, reply_markup=match_inline_keyboard(match_id))
        await bot.send_message(opp_id, text, reply_markup=match_inline_keyboard(match_id))
    else:
        cursor.execute("INSERT OR REPLACE INTO queue (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await message.answer("🔍 Raqib izlanmoqda... Boshqa o'yinchi 'Raqib topish'ni bossa, bot sizlarni biriktiradi.")
    
    conn.close()

# --- BEKOR QILISH SO'ROVI ---
@dp.callback_query(F.data.startswith("res_cancel_"))
async def request_cancel_match(call: types.CallbackQuery):
    match_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    
    active = get_active_opponent(user_id)
    if active:
        opp_id, _ = active
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_cancel_{match_id}_{user_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data=f"decline_cancel_{match_id}_{user_id}")
            ]
        ])
        
        await bot.send_message(
            opp_id, 
            "⚠️ **Raqibingiz o'yinni bekor qilishni so'rayapti.**\n\nO'yinni bekor qilishga rozimisiz?",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await call.message.answer("⏳ Raqibingizga bekor qilish so'rovi yuborildi. Javobini kuting...")
        await call.answer()
    else:
        await call.answer("Faol o'yin topilmadi.", show_alert=True)

@dp.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel(call: types.CallbackQuery):
    parts = call.data.split("_")
    match_id = int(parts[2])
    requester_id = int(parts[3])
    user_id = call.from_user.id

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user_id, requester_id))
    cursor.execute("UPDATE matches SET status = 'CANCELLED' WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

    await call.message.edit_text("❌ O'yinni bekor qilishni tasdiqladingiz. O'yin bekor qilindi.")
    await bot.send_message(requester_id, "❌ Raqibingiz bekor qilishga rozi bo'ldi. O'yin bekor qilindi.")

@dp.callback_query(F.data.startswith("decline_cancel_"))
async def decline_cancel(call: types.CallbackQuery):
    parts = call.data.split("_")
    requester_id = int(parts[3])

    await call.message.edit_text("❌ Siz bekor qilish so'rovini rad etdingiz. O'yin davom etadi.")
    await bot.send_message(requester_id, "⚠️ Raqibingiz o'yinni bekor qilishni rad etdi! O'yinni davom ettiring va natijani kiriting.")

# --- NATIJA TANLASH VA SKRINSHOT SO'RASH ---
@dp.callback_query(F.data.startswith("res_win_") | F.data.startswith("res_draw_"))
async def request_screenshot(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    outcome = parts[1]
    match_id = int(parts[2])
    
    await state.set_state(SubmitResult.waiting_for_photo)
    await state.update_data(outcome=outcome, match_id=match_id)
    
    text = (
        "📸 **Iltimos, o'yin natijasini tasdiqlaydigan skrinshot yuboring.**\n\n"
        "⚠️ **Faqat (Match History / O'yin tarixi) skrinshotini tashlang!**"
    )
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()

# --- SKRINSHOTNI ADMINGA YUBORISH ---
@dp.message(SubmitResult.waiting_for_photo, F.photo)
async def process_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    outcome = data.get('outcome')
    match_id = data.get('match_id')
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id

    pts = 3 if outcome == "win" else 1

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{user_id}_{pts}_{match_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{user_id}_{pts}_{match_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        photo_id,
        caption=f"📩 **Natija Tekshiruvi (O'yin #{match_id}):**\n👤 O'yinchi: @{message.from_user.username or user_id}\n📊 Natija: {outcome.upper()} ({pts} ochko)",
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )

    active = get_active_opponent(user_id)
    if active:
        opp_id, _ = active
        conn = sqlite3.connect('tournament.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user_id, opp_id))
        conn.commit()
        conn.close()

        await bot.send_message(opp_id, "📸 Raqibingiz natija skrinshotini yubordi. Chat yopildi, admin tekshiruvi kutilmoqda.")

    await message.answer("⏳ Skrinshot adminga yuborildi. Tekshirilgandan so'ng ochko qo'shiladi.")
    await state.clear()

# --- ANONIM CHAT ---
@dp.message(StateFilter(None), ~F.text.in_(["🎮 Raqib topish", "🏆 Leaderboard", "📊 Mening natijalarim", "⚽ Liga (Top 16)"]))
async def chat_relay(message: types.Message):
    user_id = message.from_user.id
    active = get_active_opponent(user_id)

    if active:
        opp_id, _ = active
        if message.text:
            await bot.send_message(opp_id, f"💬 Raqib: {message.text}")
        elif message.photo:
            caption = f"💬 Raqib: {message.caption}" if message.caption else "💬 Raqib [Rasm]"
            await bot.send_photo(opp_id, message.photo[-1].file_id, caption=caption)
        elif message.sticker:
            await bot.send_message(opp_id, "💬 Raqib stiker yubordi:")
            await bot.send_sticker(opp_id, message.sticker.file_id)
        elif message.voice:
            await bot.send_voice(opp_id, message.voice.file_id, caption="💬 Raqib ovozli xabar yubordi")

# --- ADMIN TASDIQLASH VA PROFILNI YANGILASH ---
@dp.callback_query(F.data.startswith("app_"))
async def approve_match(call: types.CallbackQuery):
    parts = call.data.split("_")
    u_id, pts, match_id = int(parts[1]), int(parts[2]), int(parts[3])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    # G'alaba yoki Durrang statistikasini qo'shish
    if pts == 3:
        cursor.execute("UPDATE users SET points = points + 3, wins = wins + 1, daily_games = daily_games + 1 WHERE user_id = ?", (u_id,))
    elif pts == 1:
        cursor.execute("UPDATE users SET points = points + 1, draws = draws + 1, daily_games = daily_games + 1 WHERE user_id = ?", (u_id,))
        
    cursor.execute("UPDATE matches SET status = 'APPROVED', result = ? WHERE id = ?", (f"{pts} pts", match_id))
    conn.commit()
    conn.close()

    revert_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Noto'g'ri hisob (Ochkoni ayirish)", callback_data=f"rej_{u_id}_{pts}_{match_id}")]
    ])

    await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ **Tasdiqlandi (+{pts} ochko berildi)**", reply_markup=revert_kb)
    await bot.send_message(u_id, f"🎉 Arizangiz tasdiqlandi! Hisobingizga +{pts} ochko qo'shildi.")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_match(call: types.CallbackQuery):
    parts = call.data.split("_")
    u_id, pts, match_id = int(parts[1]), int(parts[2]), int(parts[3])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    if pts == 3:
        cursor.execute("UPDATE users SET points = MAX(0, points - 3), wins = MAX(0, wins - 1), daily_games = MAX(0, daily_games - 1) WHERE user_id = ?", (u_id,))
    elif pts == 1:
        cursor.execute("UPDATE users SET points = MAX(0, points - 1), draws = MAX(0, draws - 1), daily_games = MAX(0, daily_games - 1) WHERE user_id = ?", (u_id,))
        
    cursor.execute("UPDATE matches SET status = 'REJECTED' WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ **RAD ETILDI (Ochko ayirib tashlandi)**", reply_markup=None)
    await bot.send_message(u_id, "⚠️ Natijangiz rad etildi va berilgan ochkolar olib tashlandi.")

# --- LEADERBOARD (ISHLAYDIGAN QILINDI) ---
@dp.message(F.text == "🏆 Leaderboard")
async def show_leaderboard(message: types.Message, state: FSMContext):
    await state.clear()
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 16")
    users = cursor.fetchall()
    conn.close()

    text = "🏆 **SARALASH BOSQICHI — TOP 16**\n*(7-kun yakunida ushbu 16 kishi Ligaga o'tadi)*\n\n"
    if not users:
        text += "Hozircha o'yinchilar yo'q."
    else:
        for idx, (username, points) in enumerate(users, start=1):
            text += f"{idx}. @{username} — **{points}** ochko\n"
    
    await message.answer(text, parse_mode="Markdown")

# --- MENING NATIJALARIM (RASMDAGIDEK PROFIL) ---
@dp.message(F.text == "📊 Mening natijalarim")
async def show_my_stats(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT points, wins, draws, losses FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    # Tarixni olish
    cursor.execute("SELECT result FROM matches WHERE (player1_id = ? OR player2_id = ?) AND status = 'APPROVED' ORDER BY id DESC LIMIT 5", (user_id, user_id))
    recent_matches = cursor.fetchall()
    conn.close()

    if not user_data:
        points, wins, draws, losses = 0, 0, 0, 0
    else:
        points, wins, draws, losses = user_data

    total_games = wins + draws + losses
    win_rate = round((wins / total_games) * 100) if total_games > 0 else 0

    history_text = ""
    if not recent_matches:
        history_text = "— hali o'yin yo'q —"
    else:
        for m in recent_matches:
            res = m[0]
            if "3 pts" in str(res):
                history_text += "🟢-yutdi\n"
            elif "1 pts" in str(res):
                history_text += "⚪-durang\n"
            else:
                history_text += "🔴-yutqazdi\n"

    profile_text = (
        f"🏆 **Division 10**\n"
        f"💰 **Achko:** {points}\n\n"
        f"─────────────────\n\n"
        f"📈 **Record**\n"
        f"🟢 **Wins**   » {wins}\n"
        f"🟡 **Draws**  » {draws}\n"
        f"🔴 **Losses** » {losses}\n\n"
        f"🎯 **Win Rate:** {win_rate}%\n\n"
        f"─────────────────\n\n"
        f"📋 **Match History**\n\n"
        f"{history_text}\n"
    )

    await message.answer(profile_text, parse_mode="Markdown")

# --- LIGA ---
@dp.message(F.text == "⚽ Liga (Top 16)")
async def show_league(message: types.Message, state: FSMContext):
    await state.clear()
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users WHERE in_league = 1 ORDER BY points DESC")
    league_users = cursor.fetchall()
    conn.close()

    if not league_users:
        await message.answer("⚽ **2-Bosqich: Liga** hali boshlanmadi.\n\nSaralash bosqichining 7-kuni yakunlangach, Top 16 o'yinchi bu yerga qo'shiladi.")
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
    

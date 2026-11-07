import asyncio
import sqlite3
import os
import html
import random
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ================= SOZLAMALAR =================
BOT_TOKEN = "8802613886:AAF9SvRntPSB8b1GXaNrWFy1zGJiBa7_NP8"
ADMIN_ID = 5244022908  

CHANNELS = [
    "@efuzpage",
    "@efpageshop"
]
# ===============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- WEB SERVER (Render talabi uchun) ---
async def handle_health_check(request):
    return web.Response(text="Divizion Boti ishlayapti!")

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
            extra_limit INTEGER DEFAULT 0,
            last_play_date TEXT DEFAULT '',
            last_bonus_date TEXT DEFAULT '',
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
    ''')
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
            winner_id INTEGER DEFAULT 0,
            result TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def ensure_user_exists(user_id: int, username: str):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
        (user_id, username or "O'yinchi")
    )
    conn.commit()
    conn.close()

class SubmitResult(StatesGroup):
    waiting_for_photo = State()

def main_keyboard():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎮 Raqib topish"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="🎁 Kunlik Sovg'a")],
        [KeyboardButton(text="📜 Turnir qoidalari")]
    ], resize_keyboard=True)
    return kb

def match_inline_keyboard(match_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yutdim", callback_data=f"res_win_{match_id}"),
            InlineKeyboardButton(text="🤝 Durang", callback_data=f"res_draw_{match_id}")
        ],
        [
            InlineKeyboardButton(text="🚨 Hakam chaqirish", callback_data=f"dispute_{match_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"res_cancel_{match_id}")
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

# --- 40 DAQIQALIK AVTO-OTKAZ TAYMERI ---
async def auto_cancel_match(match_id: int, p1_id: int, p2_id: int):
    await asyncio.sleep(2400) # 40 daqiqa
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM active_chats WHERE match_id = ?", (match_id,))
    active = cursor.fetchall()
    
    if active:
        cursor.execute("DELETE FROM active_chats WHERE match_id = ?", (match_id,))
        cursor.execute("UPDATE matches SET status = 'EXPIRED' WHERE id = ?", (match_id,))
        conn.commit()
        
        cancel_text = "⏱️ <b>40 daqiqa ichida natija kiritilmadi.</b> O'yin avtomatik bekor qilindi (kunlik limit kamaymadi)."
        for uid in [p1_id, p2_id]:
            try:
                await bot.send_message(uid, cancel_text, parse_mode="HTML")
            except Exception:
                pass
    conn.close()

# --- OBUNA VA BAN TEKSHIRISH MIDDLEWARE ---
async def get_unsubscribed_channels(user_id: int):
    unsubscribed = []
    for channel in CHANNELS:
        if not channel or channel.startswith("@kanalingiz"):
            continue
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                unsubscribed.append(channel)
        except Exception:
            unsubscribed.append(channel)
    return unsubscribed

def get_missing_sub_keyboard(unsubscribed_channels):
    buttons = []
    for channel in unsubscribed_channels:
        clean_ch = channel.replace('@', '')
        buttons.append([InlineKeyboardButton(text=f"📢 {channel} (Kanalga o'tish)", url=f"https://t.me/{clean_ch}")])
    buttons.append([InlineKeyboardButton(text="🔄 Qayta tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            conn = sqlite3.connect('tournament.db')
            cursor = conn.cursor()
            cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,))
            banned_row = cursor.fetchone()
            conn.close()

            if banned_row and banned_row[0] == 1:
                if isinstance(event, types.Message):
                    await event.answer("🚫 <b>Siz botdan bloklangansiz!</b> Qoidalarni buzganingiz uchun imkoniyat cheklangan.", parse_mode="HTML")
                elif isinstance(event, types.CallbackQuery):
                    await event.answer("🚫 Siz bloklangansiz!", show_alert=True)
                return

            if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
                return await handler(event, data)
            
            unsubscribed = await get_unsubscribed_channels(user.id)
            if unsubscribed:
                kb = get_missing_sub_keyboard(unsubscribed)
                warning_text = (
                    "⚠️ <b>Diqqat!</b> Botdan foydalanish uchun rasmiy kanallarga obuna bo'lishingiz shart:\n\n"
                    "👉 <b>Qayta a'zo bo'lish uchun pastdagi kanallarga bosing:</b>"
                )
                
                if isinstance(event, types.Message):
                    await event.answer(warning_text, reply_markup=kb, parse_mode="HTML")
                elif isinstance(event, types.CallbackQuery):
                    await event.message.answer(warning_text, reply_markup=kb, parse_mode="HTML")
                    await event.answer("⛔ Kanallarga a'zo bo'ling!", show_alert=True)
                return
        return await handler(event, data)

dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())

# --- START HANDLER ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    ensure_user_exists(message.from_user.id, message.from_user.username)
    
    await message.answer(
        "⚡ <b>eFootball Divizion Botiga xush kelibsiz!</b>\n\n"
        "Kunlik divizion o'yinlarida qatnashing va ochkolar yig'ing.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    unsubscribed = await get_unsubscribed_channels(call.from_user.id)
    if not unsubscribed:
        await call.message.delete()
        ensure_user_exists(call.from_user.id, call.from_user.username)
        await call.message.answer("✅ Rahmat! Barcha kanallarga obuna tasdiqlandi. /start tugmasini bosing.", reply_markup=main_keyboard())
    else:
        await call.answer("❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- TURNIR QOIDALARI ---
@dp.message(F.text == "📜 Turnir qoidalari")
async def show_rules(message: types.Message):
    rules_text = (
        "📜 <b>Divizion Turnir Qoidalari</b>\n\n"
        "1. <b>O'yin Sozlamalari:</b> Match vaqti 6 daqiqa, uzaytmalar va penaltilar seriyasi ochirilgan holda o'ynaladi.\n"
        "2. <b>Natija yuborish:</b> O'yin tugagach, darhol Match History skrinshotini yuboring.\n"
        "3. <b>40 daqiqa taymer:</b> Raqib topilgandan keyin 40 daqiqa ichida natija kiritilmasa, o'yin avtomatik bekor qilinadi.\n"
        "4. <b>Limitlar:</b> Har bir o'yinchi kuniga 20 ta o'yin o'tkazishi mumkin.\n"
        "5. <b>Halollik:</b> Soxta skrinshot tashlaganlar va haqorat qilganlar botdan ban qilinadi."
    )
    await message.answer(rules_text, parse_mode="HTML")

# --- KUNLIK SOVG'A ---
@dp.message(F.text == "🎁 Kunlik Sovg'a")
async def daily_bonus(message: types.Message):
    user_id = message.from_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_bonus_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    last_bonus = row[0] if row else ""
    if last_bonus == today_str:
        await message.answer("⚠️ <b>Bugun kunlik sovg'ani olib bo'ldingiz!</b> Ertaga yana urinib ko'ring.", parse_mode="HTML")
        conn.close()
        return

    reward_type = random.choice(["limit", "points"])
    
    if reward_type == "limit":
        cursor.execute("UPDATE users SET extra_limit = extra_limit + 3, last_bonus_date = ? WHERE user_id = ?", (today_str, user_id))
        msg = "🎁 <b>OMAD!</b> Sizga bugun uchun <b>+3 ta qo'shimcha o'yin limiti</b> berildi! 🚀"
    else:
        cursor.execute("UPDATE users SET points = points + 5, last_bonus_date = ? WHERE user_id = ?", (today_str, user_id))
        msg = "🎁 <b>OMAD!</b> Hisobingizga <b>+5 ochko</b> qo'shildi! 🏆"

    conn.commit()
    conn.close()
    await message.answer(msg, parse_mode="HTML")

# --- RAQIB TOPISH ---
@dp.message(F.text == "🎮 Raqib topish")
async def find_opponent(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    ensure_user_exists(user_id, username)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if get_active_opponent(user_id):
        await message.answer("⚠️ Sizda hozirda faol o'yin mavjud! Avval o'yinni yakunlang yoki bekor qiling.")
        return

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_games, extra_limit, last_play_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    daily_games, extra_lim, l_date = row[0] or 0, row[1] or 0, row[2] or ""

    if l_date != today_str:
        cursor.execute("UPDATE users SET daily_games = 0, extra_limit = 0, last_play_date = ? WHERE user_id = ?", (today_str, user_id))
        conn.commit()
        daily_games = 0
        extra_lim = 0

    max_allowed = 20 + extra_lim
    if daily_games >= max_allowed:
        await message.answer(f"⛔ <b>Bugungi ({max_allowed} ta) o'yin limitidan foydalanib bo'ldingiz!</b>", parse_mode="HTML")
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
        conn.close()

        asyncio.create_task(auto_cancel_match(match_id, user_id, opp_id))

        text = (
            "✅ <b>Raqib topildi!</b> Endi u bilan shu chat orqali anonim yozishingiz mumkin.\n\n"
            "⏱️ <i>40 daqiqa ichida natija kiritilmasa o'yin avtomatik bekor qilinadi!</i>\n"
            "O'yin tugagach natijani belgilang:"
        )
        
        await message.answer(text, reply_markup=match_inline_keyboard(match_id), parse_mode="HTML")
        await bot.send_message(opp_id, text, reply_markup=match_inline_keyboard(match_id), parse_mode="HTML")
    else:
        cursor.execute("INSERT OR REPLACE INTO queue (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        
        search_msg = await message.answer("🔍 <b>Raqib izlanmoqda...</b>\n⏱️ (1 daqiqa ichida raqib topilmasa izlash bekor qilinadi)", parse_mode="HTML")
        
        await asyncio.sleep(60)
        
        conn2 = sqlite3.connect('tournament.db')
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT user_id FROM queue WHERE user_id = ?", (user_id,))
        in_queue = cursor2.fetchone()
        
        if in_queue:
            cursor2.execute("DELETE FROM queue WHERE user_id = ?", (user_id,))
            conn2.commit()
            conn2.close()
            try:
                await search_msg.edit_text("⏱️ <b>1 daqiqa ichida raqib topilmadi.</b> Izlash bekor qilindi.", parse_mode="HTML")
            except Exception:
                await message.answer("⏱️ <b>1 daqiqa ichida raqib topilmadi.</b> Izlash bekor qilindi.", parse_mode="HTML")
        else:
            conn2.close()

# --- HAKAM CHAQIRISH ---
@dp.callback_query(F.data.startswith("dispute_"))
async def call_referee(call: types.CallbackQuery):
    match_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    username = call.from_user.username or str(user_id)
    
    active = get_active_opponent(user_id)
    if active:
        opp_id, _ = active
        admin_text = (
            f"🚨 <b>HAKAM CHAQIRILDI (Match #{match_id}):</b>\n\n"
            f"👤 Chaqirgan: @{html.escape(username)} (ID: `{user_id}`)\n"
            f"👤 Raqib ID: `{opp_id}`"
        )
        ban_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🚫 Raqibni Ban Qilish ({opp_id})", callback_data=f"ban_user_{opp_id}")]
        ])
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=ban_kb, parse_mode="HTML")
        await call.message.answer("🚨 Hakamga xabar yuborildi! Tez orada vaziyat o'rganiladi.")
        await call.answer()
    else:
        await call.answer("Faol o'yin topilmadi.", show_alert=True)

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
            "⚠️ <b>Raqibingiz o'yinni bekor qilishni so'rayapti.</b>\n\nO'yinni bekor qilishga rozimisiz?",
            reply_markup=kb,
            parse_mode="HTML"
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
    await bot.send_message(requester_id, "⚠️ Raqibingiz o'yinni bekor qilishni rad etdi! O'yinni davom ettiring.")

# --- NATIJA TANLASH VA SKRINSHOT SO'RASH ---
@dp.callback_query(F.data.startswith("res_win_") | F.data.startswith("res_draw_"))
async def request_screenshot(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    outcome = parts[1]
    match_id = int(parts[2])
    
    await state.set_state(SubmitResult.waiting_for_photo)
    await state.update_data(outcome=outcome, match_id=match_id)
    
    text = (
        "📸 <b>Iltimos, o'yin natijasini tasdiqlaydigan skrinshot yuboring.</b>\n\n"
        "⚠️ <b>Faqat Match History skrinshotini tashlang!</b>"
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# --- SKRINSHOTNI ADMINGA YUBORISH ---
@dp.message(SubmitResult.waiting_for_photo, F.photo)
async def process_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    outcome = data.get('outcome')
    match_id = data.get('match_id')
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id

    ensure_user_exists(user_id, message.from_user.username)
    pts = 3 if outcome == "win" else 1

    active = get_active_opponent(user_id)
    opp_id = active[0] if active else 0

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{user_id}_{pts}_{match_id}_{opp_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{user_id}_{pts}_{match_id}_{opp_id}")
        ],
        [
            InlineKeyboardButton(text=f"🚫 {user_id} ni Ban qilish", callback_data=f"ban_user_{user_id}")
        ]
    ])

    user_name_safe = html.escape(message.from_user.username or str(user_id))

    try:
        await bot.send_photo(
            ADMIN_ID,
            photo_id,
            caption=f"📩 <b>Natija Tekshiruvi (O'yin #{match_id}):</b>\n👤 O'yinchi: @{user_name_safe} (ID: `{user_id}`)\n📊 Da'vo: {outcome.upper()} ({pts} ochko)",
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Admin'ga xabar yuborishda xatolik: {e}")

    if active:
        conn = sqlite3.connect('tournament.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_chats WHERE user_id IN (?, ?)", (user_id, opp_id))
        conn.commit()
        conn.close()

        await bot.send_message(opp_id, "📸 Raqibingiz natija skrinshotini yubordi. Chat yopildi, admin tekshiruvi kutilmoqda.")

    await message.answer("⏳ Skrinshot adminga yuborildi. Tekshirilgandan so'ng ochkolar hisoblanadi.")
    await state.clear()

# --- ANONIM CHAT ---
@dp.message(
    StateFilter(None), 
    ~F.text.startswith("/"), 
    ~F.text.in_(["🎮 Raqib topish", "🏆 Leaderboard", "📊 Mening natijalarim", "🎁 Kunlik Sovg'a", "📜 Turnir qoidalari"])
)
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
            
# --- ADMIN TASDIQLASH ---
@dp.callback_query(F.data.startswith("app_"))
async def approve_match(call: types.CallbackQuery):
    parts = call.data.split("_")
    u_id, pts, match_id = int(parts[1]), int(parts[2]), int(parts[3])
    opp_id = int(parts[4]) if len(parts) > 4 else 0

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    if pts == 3:
        cursor.execute("UPDATE users SET points = points + 3, wins = wins + 1, daily_games = daily_games + 1 WHERE user_id = ?", (u_id,))
        if opp_id:
            cursor.execute("UPDATE users SET losses = losses + 1, daily_games = daily_games + 1 WHERE user_id = ?", (opp_id,))
        winner = u_id
    elif pts == 1:
        cursor.execute("UPDATE users SET points = points + 1, draws = draws + 1, daily_games = daily_games + 1 WHERE user_id = ?", (u_id,))
        if opp_id:
            cursor.execute("UPDATE users SET points = points + 1, draws = draws + 1, daily_games = daily_games + 1 WHERE user_id = ?", (opp_id,))
        winner = 0

    cursor.execute("UPDATE matches SET status = 'APPROVED', winner_id = ?, result = ? WHERE id = ?", (winner, f"{pts} pts", match_id))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ <b>Tasdiqlandi!</b>", reply_markup=None, parse_mode="HTML")
    await bot.send_message(u_id, f"🎉 Arizangiz tasdiqlandi! Hisobingizga +{pts} ochko qo'shildi.")
    if opp_id:
        await bot.send_message(opp_id, "📊 O'yin natijasi admin tomonidan tasdiqlandi va statistikangizga qo'shildi.")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_match(call: types.CallbackQuery):
    parts = call.data.split("_")
    u_id, match_id = int(parts[1]), int(parts[3])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE matches SET status = 'REJECTED' WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ <b>RAD ETILDI</b>", reply_markup=None, parse_mode="HTML")
    await bot.send_message(u_id, "⚠️ Natijangiz rad etildi.")

# --- BAN TIZIMI ---
@dp.callback_query(F.data.startswith("ban_user_"))
async def ban_user_callback(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[2])
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    
    await call.answer("🚫 Foydalanuvchi bloklandi!", show_alert=True)
    await bot.send_message(target_id, "🚫 Qoidalarni buzganingiz uchun botdan butunlay bloklandingiz!")

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Foydalanish: `/ban USER_ID`", parse_mode="Markdown")
        return
    target_id = int(args[1])
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ User ID `{target_id}` bloklandi.")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Foydalanish: `/unban USER_ID`", parse_mode="Markdown")
        return
    target_id = int(args[1])
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ User ID `{target_id}` blokdan chiqarildi.")

@dp.message(Command("addpoints"))
async def cmd_addpoints(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Foydalanish: `/addpoints @username ochko`", parse_mode="Markdown")
        return
    
    target_username = args[1].replace("@", "").strip()
    pts_to_add = int(args[2])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)", (target_username,))
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ @{target_username} topilmadi!")
        conn.close()
        return

    uid = row[0]
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (pts_to_add, uid))
    conn.commit()
    conn.close()

    await message.answer(f"✅ @{target_username} 'ga +{pts_to_add} ochko qo'shildi!")
    try:
        await bot.send_message(uid, f"🎉 Admin tomonidan hisobingizga <b>+{pts_to_add} ochko</b> qo'shildi!", parse_mode="HTML")
    except Exception:
        pass

@dp.message(Command("removepoints"))
async def cmd_removepoints(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Foydalanish: `/removepoints @username 10`", parse_mode="Markdown")
        return
    
    target = args[1].replace("@", "").strip()
    pts_to_sub = int(args[2])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE LOWER(username) = LOWER(?)", (target,))
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ Bazada '{args[1]}' topilmadi!")
        conn.close()
        return

    uid, uname = row[0], row[1]
    cursor.execute("UPDATE users SET points = MAX(0, points - ?) WHERE user_id = ?", (pts_to_sub, uid))
    conn.commit()
    conn.close()

    await message.answer(f"✅ @{html.escape(uname or str(uid))} 'dan <b>-{pts_to_sub} ochko</b> ayirildi!", parse_mode="HTML")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Foydalanish: `/broadcast Xabar matni`", parse_mode="Markdown")
        return

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent, failed = 0, 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 <b>ADMIN BILDIRISHNOMASI:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(f"📊 Xabar tarqatildi:\n✅ Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")

# --- LEADERBOARD ---
@dp.message(F.text == "🏆 Leaderboard")
async def show_leaderboard(message: types.Message, state: FSMContext):
    await state.clear()
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 20")
    users = cursor.fetchall()
    conn.close()

    text = "🏆 <b>DIVIZION — TOP O'YINCHILAR</b>\n\n"
    if not users:
        text += "Hozircha o'yinchilar yo'q."
    else:
        for idx, (username, points) in enumerate(users, start=1):
            safe_name = html.escape(username or "O'yinchi")
            text += f"{idx}. @{safe_name} — <b>{points}</b> ochko\n"
    
    await message.answer(text, parse_mode="HTML")

# --- MENING NATIJALARIM ---
@dp.message(F.text == "📊 Mening natijalarim")
async def show_my_stats(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    ensure_user_exists(user_id, message.from_user.username)
    
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT points, wins, draws, losses FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    cursor.execute("SELECT winner_id, result FROM matches WHERE (player1_id = ? OR player2_id = ?) AND status = 'APPROVED' ORDER BY id DESC LIMIT 5", (user_id, user_id))
    recent_matches = cursor.fetchall()
    conn.close()

    points, wins, draws, losses = user_data if user_data else (0, 0, 0, 0)
    total_games = wins + draws + losses
    win_rate = round((wins / total_games) * 100) if total_games > 0 else 0

    history_text = ""
    if not recent_matches:
        history_text = "— hali o'yin yo'q —"
    else:
        for w_id, res in recent_matches:
            if w_id == user_id:
                history_text += "🟢 Yutdi (+3 pts)\n"
            elif w_id == 0:
                history_text += "⚪ Durang (+1 pts)\n"
            else:
                history_text += "🔴 Yutqazdi (0 pts)\n"

    profile_text = (
        f"👤 <b>Profil:</b> @{html.escape(message.from_user.username or 'O`yinchi')}\n"
        f"💰 <b>Jami ochkolar:</b> {points}\n\n"
        f"─────────────────\n"
        f"📈 <b>Statistika:</b>\n"
        f"🟢 <b>G'alaba:</b> {wins}\n"
        f"🟡 <b>Durang:</b> {draws}\n"
        f"🔴 <b>Mag'lubiyat:</b> {losses}\n"
        f"🎯 <b>Win Rate:</b> {win_rate}%\n"
        f"─────────────────\n"
        f"📋 <b>Oxirgi 5 o'yin tarixi:</b>\n\n"
        f"{history_text}"
    )

    await message.answer(profile_text, parse_mode="HTML")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

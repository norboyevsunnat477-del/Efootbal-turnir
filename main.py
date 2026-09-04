import asyncio
import sqlite3
import os
import html
import json
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ================= SOZLAMALAR =================
BOT_TOKEN = "BOT_TOKENINI_SHUYERGA_YOZING"
ADMIN_ID = 123456789  
CHANNEL_USERNAME = "@kanalingiz_username"
RENDER_APP_URL = "https://efootbal-turnir.onrender.com"
# ===============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- MINI APP HTML INTERFEYSI ---
LEAGUE_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>eFootball 50k Liga</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: #0d1117; color: #c9d1d9; padding: 12px; }
        .header { text-align: center; padding: 15px 10px; background: linear-gradient(135deg, #1f2937, #111827); border-radius: 12px; border: 1px solid #374151; margin-bottom: 15px; }
        .header h1 { font-size: 20px; color: #f59e0b; margin-bottom: 4px; }
        .header p { font-size: 13px; color: #9ca3af; }
        .tabs { display: flex; gap: 8px; margin-bottom: 15px; }
        .tab-btn { flex: 1; padding: 10px; background: #161b22; border: 1px solid #30363d; color: #8b949e; border-radius: 8px; font-weight: bold; cursor: pointer; text-align: center; }
        .tab-btn.active { background: #238636; color: white; border-color: #2ea043; }
        .content-section { display: none; }
        .content-section.active { display: block; }
        table { width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; border: 1px solid #30363d; font-size: 13px; }
        th { background: #21262d; color: #8b949e; text-align: left; padding: 10px; font-weight: 600; }
        td { padding: 10px; border-bottom: 1px solid #21262d; }
        tr:last-child td { border-bottom: none; }
        .rank { font-weight: bold; width: 25px; text-align: center; }
        .top-1 { color: #f59e0b; }
        .top-2 { color: #d1d5db; }
        .top-3 { color: #b45309; }
        .points { font-weight: bold; color: #10b981; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
        .match-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px dashed #30363d; }
        .match-row:last-child { border-bottom: none; }
        .player { flex: 1; font-weight: 500; }
        .score { font-weight: bold; padding: 2px 8px; background: #21262d; border-radius: 4px; color: #38bdf8; }
        .round-title { font-size: 14px; font-weight: bold; color: #f59e0b; margin-bottom: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏆 TOP 16 LIGA</h1>
        <p>🎁 Mukofot jamg'armasi: <b>50 000 SO'M</b></p>
    </div>

    <div class="tabs">
        <div class="tab-btn active" onclick="switchTab('table')">📊 Jadval</div>
        <div class="tab-btn" onclick="switchTab('fixtures')">📅 Turlar</div>
    </div>

    <div id="table-section" class="content-section active">
        <table>
            <thead>
                <tr>
                    <th>№</th>
                    <th>O'yinchi</th>
                    <th>O'O</th>
                    <th>G/D/M</th>
                    <th>Ochko</th>
                </tr>
            </thead>
            <tbody id="standings-body">
                <tr><td colspan="5" style="text-align:center;">Yuklanmoqda...</td></tr>
            </tbody>
        </table>
    </div>

    <div id="fixtures-section" class="content-section">
        <div id="fixtures-body">
            <div style="text-align:center; padding:20px;">Yuklanmoqda...</div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
            if(tab === 'table') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('table-section').classList.add('active');
            } else {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('fixtures-section').classList.add('active');
            }
        }

        async function loadData() {
            try {
                const res = await fetch('/api/league');
                const data = await res.json();
                
                const tbody = document.getElementById('standings-body');
                if(!data.standings || data.standings.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Liga hali boshlanmadi. Top 16 kutilmoqda.</td></tr>';
                } else {
                    tbody.innerHTML = data.standings.map((p, i) => {
                        let rankClass = i === 0 ? 'top-1' : (i === 1 ? 'top-2' : (i === 2 ? 'top-3' : ''));
                        return `<tr>
                            <td class="rank ${rankClass}">${i+1}</td>
                            <td>@${p.username}</td>
                            <td>${p.wins + p.draws + p.losses}</td>
                            <td>${p.wins}/${p.draws}/${p.losses}</td>
                            <td class="points">${p.points}</td>
                        </tr>`;
                    }).join('');
                }

                const fixBody = document.getElementById('fixtures-body');
                if(!data.fixtures || data.fixtures.length === 0) {
                    fixBody.innerHTML = '<div class="card" style="text-align:center;">Turlar jadvali hali tuzilmadi.</div>';
                } else {
                    let html = '';
                    for(let r = 1; r <= 16; r++) {
                        let matches = data.fixtures.filter(m => m.round === r);
                        if(matches.length > 0) {
                            html += `<div class="card"><div class="round-title">⚽ ${r}-Tur</div>`;
                            matches.forEach(m => {
                                html += `<div class="match-row">
                                    <span class="player">@${m.p1}</span>
                                    <span class="score">${m.score}</span>
                                    <span class="player" style="text-align:right;">@${m.p2}</span>
                                </div>`;
                            });
                            html += '</div>';
                        }
                    }
                    fixBody.innerHTML = html || '<div class="card" style="text-align:center;">Hali turlar o`yinlari yo`q.</div>';
                }
            } catch(e) {
                console.error(e);
            }
        }

        loadData();
    </script>
</body>
</html>
"""

# --- WEB SERVER & API ENDPOINTS ---
async def handle_health_check(request):
    return web.Response(text="Bot va Mini App ishlayapti!")

async def handle_league_app(request):
    return web.Response(text=LEAGUE_HTML, content_type='text/html')

async def handle_league_api(request):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, points, wins, draws, losses FROM users WHERE in_league = 1 ORDER BY points DESC, wins DESC")
    users = cursor.fetchall()
    standings = [{"username": u[0], "points": u[1], "wins": u[2], "draws": u[3], "losses": u[4]} for u in users]

    cursor.execute("""
        SELECT round_num, u1.username, u2.username, score_text 
        FROM league_fixtures lf
        LEFT JOIN users u1 ON lf.player1_id = u1.user_id
        LEFT JOIN users u2 ON lf.player2_id = u2.user_id
        ORDER BY round_num ASC
    """)
    fixtures_data = cursor.fetchall()
    conn.close()

    fixtures = [{"round": f[0], "p1": f[1] or "O'yinchi1", "p2": f[2] or "O'yinchi2", "score": f[3] or "vs"} for f in fixtures_data]

    return web.json_response({"standings": standings, "fixtures": fixtures})

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/liga', handle_league_app)
    app.router.add_get('/api/league', handle_league_api)
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
            last_play_date TEXT DEFAULT '',
            in_league INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'wins' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN wins INTEGER DEFAULT 0")
    if 'draws' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN draws INTEGER DEFAULT 0")
    if 'losses' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0")
    if 'last_play_date' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_play_date TEXT DEFAULT ''")

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS league_fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_num INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            score_text TEXT DEFAULT 'vs',
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

# --- START HANDLER ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    ensure_user_exists(message.from_user.id, message.from_user.username)
    
    if not await check_sub(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
        ])
        await message.answer("⚠️ Botdan foydalanish uchun kanalimizga a'zo bo'ling:", reply_markup=kb)
        return

    await message.answer(
        "⚡ <b>eFootball Turnir Botiga xush kelibsiz!</b>\n\n"
        "1-bosqich (Saralash) ketyapti. Kuniga 5 tagacha raqib topib o'ynashingiz mumkin.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        ensure_user_exists(call.from_user.id, call.from_user.username)
        await call.message.answer("✅ Rahmat! Obuna tasdiqlandi. /start tugmasini bosing.", reply_markup=main_keyboard())
    else:
        await call.answer("❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

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
    
    cursor.execute("SELECT daily_games, last_play_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    daily_games = 0
    if row:
        d_games, l_date = row[0] or 0, row[1] or ""
        if l_date != today_str:
            cursor.execute("UPDATE users SET daily_games = 0, last_play_date = ? WHERE user_id = ?", (today_str, user_id))
            conn.commit()
            daily_games = 0
        else:
            daily_games = d_games

    if daily_games >= 5:
        await message.answer("⛔ <b>Bugungi 5 ta o'yin limitidan foydalanib bo'ldingiz!</b> Ertaga yana urinib ko'ring.", parse_mode="HTML")
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

        text = (
            "✅ <b>Raqib topildi!</b> Endi u bilan shu chat orqali anonim yozishingiz mumkin.\n"
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
                await search_msg.edit_text("⏱️ <b>1 daqiqa ichida raqib topilmadi.</b> Izlash bekor qilindi (kunlik limit kamaymadi).", parse_mode="HTML")
            except Exception:
                await message.answer("⏱️ <b>1 daqiqa ichida raqib topilmadi.</b> Izlash bekor qilindi (kunlik limit kamaymadi).", parse_mode="HTML")
        else:
            conn2.close()

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
        "📸 <b>Iltimos, o'yin natijasini tasdiqlaydigan skrinshot yuboring.</b>\n\n"
        "⚠️ <b>Faqat (Match History / O'yin tarixi) skrinshotini tashlang!</b>"
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

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_{user_id}_{pts}_{match_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_{user_id}_{pts}_{match_id}")
        ]
    ])

    user_name_safe = html.escape(message.from_user.username or str(user_id))

    try:
        await bot.send_photo(
            ADMIN_ID,
            photo_id,
            caption=f"📩 <b>Natija Tekshiruvi (O'yin #{match_id}):</b>\n👤 O'yinchi: @{user_name_safe}\n📊 Natija: {outcome.upper()} ({pts} ochko)",
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Admin'ga xabar yuborishda xatolik: {e}")

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

# --- ADMIN TASDIQLASH / RAD ETISH ---
@dp.callback_query(F.data.startswith("app_"))
async def approve_match(call: types.CallbackQuery):
    parts = call.data.split("_")
    u_id, pts, match_id = int(parts[1]), int(parts[2]), int(parts[3])

    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
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

    await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ <b>Tasdiqlandi (+{pts} ochko berildi)</b>", reply_markup=revert_kb, parse_mode="HTML")
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

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ <b>RAD ETILDI (Ochko ayirib tashlandi)</b>", reply_markup=None, parse_mode="HTML")
    await bot.send_message(u_id, "⚠️ Natijangiz rad etildi va berilgan ochkolar olib tashlandi.")

# --- LEADERBOARD ---
@dp.message(F.text == "🏆 Leaderboard")
async def show_leaderboard(message: types.Message, state: FSMContext):
    await state.clear()
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 16")
    users = cursor.fetchall()
    conn.close()

    text = "🏆 <b>SARALASH BOSQICHI — TOP 16</b>\n<i>(7-kun yakunida ushbu 16 kishi Ligaga o'tadi)</i>\n\n"
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
        f"🏆 <b>Division 10</b>\n"
        f"💰 <b>Achko:</b> {points}\n\n"
        f"─────────────────\n\n"
        f"📈 <b>Record</b>\n"
        f"🟢 <b>Wins</b>   » {wins}\n"
        f"🟡 <b>Draws</b>  » {draws}\n"
        f"🔴 <b>Losses</b> » {losses}\n\n"
        f"🎯 <b>Win Rate:</b> {win_rate}%\n\n"
        f"─────────────────\n\n"
        f"📋 <b>Match History</b>\n\n"
        f"{history_text}\n"
    )

    await message.answer(profile_text, parse_mode="HTML")

# --- LIGA MINI APP TUGMASI ---
@dp.message(F.text == "⚽ Liga (Top 16)")
async def show_league(message: types.Message, state: FSMContext):
    await state.clear()
    
    app_url = f"{RENDER_APP_URL}/liga"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 LIGA MINI APP'INI OCHISH", web_app=WebAppInfo(url=app_url))]
    ])
    
    await message.answer(
        "⚽ <b>2-Bosqich: Liga (Top 16)</b>\n\n"
        "Jadval va turlar matchlarini Mini App ko'rinishida ochish uchun pastdagi tugmani bosing:",
        reply_markup=kb,
        parse_mode="HTML"
    )

# --- ADMIN BUYRUG'I: TOP 16 NI LIGAGA O'TKAZISH ---
@dp.message(Command("start_league"))
async def start_league_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id FROM users ORDER BY points DESC LIMIT 16")
    top_users = [row[0] for row in cursor.fetchall()]
    
    if len(top_users) < 2:
        await message.answer("⚠️ Ligani boshlash uchun kamida 2 ta o'yinchi kerak!")
        conn.close()
        return

    cursor.execute("UPDATE users SET in_league = 0, points = 0, wins = 0, draws = 0, losses = 0")
    for u_id in top_users:
        cursor.execute("UPDATE users SET in_league = 1 WHERE user_id = ?", (u_id,))

    cursor.execute("DELETE FROM league_fixtures")
    round_num = 1
    for i in range(len(top_users)):
        for j in range(i + 1, len(top_users)):
            cursor.execute("INSERT INTO league_fixtures (round_num, player1_id, player2_id) VALUES (?, ?, ?)",
                           (round_num, top_users[i], top_users[j]))
            round_num += 1

    conn.commit()
    conn.close()
    await message.answer(f"🎉 **Liga rasman boshlandi!** Top {len(top_users)} o'yinchilar Ligaga o'tkazildi va Mini App yangilandi.")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

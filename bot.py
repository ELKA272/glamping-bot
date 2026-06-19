import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
import calendar

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, MessageHandler, filters,
)
from telegram.helpers import escape_markdown as esc

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────
BOT_TOKEN = "8613215775:AAHJcqaPOgkXiZw_XFT87PX_mnm2mIgp-ok"
ADMIN_PHONE = "+7 902 872 48 03"
ADMIN_USERNAME = "@shantaram_2722"
ADMIN_CHANNEL = "@a_run_of_luck"
SITE_URL = "удачная-территория.рф"
CONFIG_FILE = Path("admin_config.json")

def load_admin():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text()).get("admin_chat_id", 0)
    return 0

def save_admin(cid):
    CONFIG_FILE.write_text(json.dumps({"admin_chat_id": cid}))

ADMIN_CHAT_ID = load_admin()

# ── Данные ──────────────────────────────────────────────────────────
HOUSES = {
    "meeting": {"name": "Дом встреч", "price": 17000, "wd_price": 15000, "cap": 4,
                 "desc": "Просторный домик с собственной баней. Идеален для компании.",
                 "features": ["🛁 Баня", "🛏 4 места", "🌿 Терраса"], "icon": "🔥"},
    "time": {"name": "Узел времени", "price": 12000, "wd_price": 10000, "cap": 4,
              "desc": "Уютный домик, где время замедляет свой бег.",
              "features": ["☕ Кофе-станция", "🛏 4 места", "🌿 Терраса"], "icon": "⏳"},
    "mirror": {"name": "Зеркало леса", "price": 12000, "wd_price": 10000, "cap": 4,
                "desc": "Панорамные окна с завораживающим видом на лес.",
                "features": ["🪟 Панорамный вид", "🛏 4 места", "🌿 Терраса"], "icon": "🪞"},
    "peak": {"name": "Вершина уДачи", "price": 12000, "wd_price": 10000, "cap": 4,
              "desc": "Самый уединённый домик на возвышенности. Восходы с террасы.",
              "features": ["🌅 Вид на закат", "🛏 4 места", "🌿 Терраса"], "icon": "⛰"},
}

SERVICES = {
    "bath": {"name": "Баня", "price": 5000, "icon": "🛁"},
    "excursion": {"name": "Экскурсия", "price": 3500, "icon": "🚶"},
    "chaan": {"name": "Чан", "price": 2000, "icon": "🪔"},
}

# ── Состояния ───────────────────────────────────────────────────────
(SEL_HOUSE, SEL_CHECKIN, SEL_CHECKOUT, SEL_SERVICES, CONFIRM, NAME, PHONE, COMMENT, ADMIN_MSG) = range(9)

# ── Хранилище ───────────────────────────────────────────────────────
BOOK_FILE = Path("bookings.json")

def load_bookings():
    return json.loads(BOOK_FILE.read_text()) if BOOK_FILE.exists() else []

def save_booking(data):
    bks = load_bookings()
    data["id"] = len(bks) + 1
    data["user_id"] = data.get("user_id", 0)
    data["created_at"] = datetime.now().isoformat()
    data["status"] = "active"
    bks.append(data)
    BOOK_FILE.write_text(json.dumps(bks, ensure_ascii=False, indent=2))
    return data["id"]

def upd_booking(bid, upd):
    bks = load_bookings()
    for b in bks:
        if b["id"] == bid:
            b.update(upd)
            break
    BOOK_FILE.write_text(json.dumps(bks, ensure_ascii=False, indent=2))

def is_wd(d):
    return d.weekday() < 4

# ── Клавиатуры ─────────────────────────────────────────────────────

def main_kb():
    return ReplyKeyboardMarkup([
        ["🏡 Домики", "📅 Бронь", "📋 Мои брони"],
        ["❓ FAQ", "📞 Связь с админом", "📱 Контакты"],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)

def houses_ikb():
    kb = [[InlineKeyboardButton(f"{h['icon']} {h['name']} — {h['price']}₽", callback_data=f"h_{k}")] for k, h in HOUSES.items()]
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(kb)

def calendar_kb(year, month, prefix):
    kb = []
    kb.append([InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")])
    week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(d, callback_data="ignore") for d in week])
    mc = calendar.monthcalendar(year, month)
    today = date.today()
    for w in mc:
        row = []
        for d in w:
            if d == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                dt = date(year, month, d)
                if dt < today:
                    row.append(InlineKeyboardButton("✖", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(str(d), callback_data=f"{prefix}_{dt.isoformat()}"))
        kb.append(row)
    prev = (month - 1) if month > 1 else 12
    py = year if month > 1 else year - 1
    nxt = (month + 1) if month < 12 else 1
    ny = year if month < 12 else year + 1
    kb.append([
        InlineKeyboardButton("◀", callback_data=f"cal_{prefix}_{py}_{prev}"),
        InlineKeyboardButton("Сегодня", callback_data=f"cal_{prefix}_{today.year}_{today.month}"),
        InlineKeyboardButton("▶", callback_data=f"cal_{prefix}_{ny}_{nxt}"),
    ])
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(kb)

def services_ikb(selected):
    kb = []
    for k, s in SERVICES.items():
        mark = "✅" if k in selected else "⬜"
        kb.append([InlineKeyboardButton(f"{mark} {s['icon']} {s['name']} +{s['price']}₽", callback_data=f"sv_{k}")])
    kb.append([InlineKeyboardButton("✅ Готово", callback_data="sv_done")])
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(kb)

def confirm_ikb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="cnf_yes")],
        [InlineKeyboardButton("🔄 Заново", callback_data="cnf_restart")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])

def book_actions_ikb(bid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить бронь", callback_data=f"cl_{bid}")],
        [InlineKeyboardButton("📞 Связаться с админом", callback_data=f"adm_{bid}")],
    ])

# ── Команды ─────────────────────────────────────────────────────────

async def start(update: Update, ctx):
    u = update.effective_user
    await update.message.reply_text(
        f"🌲 Добро пожаловать, {u.first_name}!\n\n"
        "🏡 <b>уДачная территория</b> — глэмпинг в парке «Оленьи ручьи»\n\n"
        "👇 Меню:",
        parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def set_admin(update: Update, ctx):
    save_admin(update.effective_user.id)
    global ADMIN_CHAT_ID
    ADMIN_CHAT_ID = update.effective_user.id
    await update.message.reply_text(
        "✅ Вы назначены администратором!\n\n"
        "📋 Все заявки и сообщения от гостей приходят вам.\n"
        "Команды:\n"
        "/bookings — все заявки\n"
        "/reply <id> <текст> — ответ гостю")

async def houses_cmd(update: Update, ctx):
    for k, h in HOUSES.items():
        wd = f" (будни: {h['wd_price']}₽)" if h['wd_price'] != h['price'] else ""
        t = (
            f"{h['icon']} <b>{h['name']}</b>\n"
            f"▫️ {h['cap']} гостя | {h['desc']}\n"
            f"▫️ {h['price']}₽/сутки{wd}\n"
            f"▫️ {', '.join(h['features'])}\n"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 Забронировать {h['icon']}", callback_data=f"h_{k}")]
        ])
        await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
    t = (
        "🛁 <b>Дополнительные услуги:</b>\n"
        "Баня 5 000₽ | Экскурсия 3 500₽ | Чан 2 000₽\n\n"
        "💡 Будни (ПН-ЧТ) — скидка на проживание!"
    )
    await update.message.reply_text(t, parse_mode=ParseMode.HTML)

async def faq_cmd(update: Update, ctx):
    t = (
        "❓ <b>Часто спрашивают:</b>\n\n"
        "📍 <b>Где вы находитесь?</b>\n"
        "Природный парк «Оленьи ручьи», Свердловская область.\n"
        "От Екатеринбурга ~2 часа на машине.\n\n"
        "🕐 <b>Заезд/выезд?</b>\n"
        "Заезд с 14:00, выезд до 12:00.\n\n"
        "🛁 <b>Баня, экскурсии, чан?</b>\n"
        "• Баня — 5 000₽ (в Доме встреч или отдельно)\n"
        "• Экскурсия по парку — 3 500₽\n"
        "• Чан (купка под открытым небом) — 2 000₽\n\n"
        "👨‍👩‍👧‍👦 <b>Сколько гостей?</b>\n"
        "До 4 человек в каждом домике.\n\n"
        "🐕 <b>Можно с собаками?</b>\n"
        "Да, по согласованию при бронировании.\n\n"
        "🚗 <b>Как добраться?</b>\n"
        "На машине от Екатеринбурга ~2 ч.\n"
        "Координаты пришлём после брони.\n\n"
        "💰 <b>Способы оплаты?</b>\n"
        "Наличные, перевод на карту.\n\n"
        "🍽 <b>Есть ли еда?</b>\n"
        "В домиках есть мини-кухня. Кафе рядом нет — "
        "рекомендуем брать продукты с собой.\n\n"
        "🎉 <b>Можно ли отметить праздник?</b>\n"
        "Да, Дом встреч отлично подходит для компаний.\n\n"
        "📞 <b>Остались вопросы?</b>\n"
        f"Звоните {ADMIN_PHONE} или пишите {ADMIN_USERNAME}"
    )
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def contacts_cmd(update: Update, ctx):
    await update.message.reply_text(
        "📞 <b>Контакты:</b>\n\n"
        f"📱 <b>Телефон:</b> {ADMIN_PHONE}\n"
        f"📩 <b>Telegram:</b> {ADMIN_USERNAME}\n"
        f"📢 <b>Канал:</b> {ADMIN_CHANNEL}\n"
        f"🌐 <b>Сайт:</b> {SITE_URL}\n\n"
        f"📅 Забронировать — через меню бота",
        parse_mode=ParseMode.HTML)

async def my_bookings(update: Update, ctx):
    uid = update.effective_user.id
    bks = [b for b in load_bookings() if b.get("user_id") == uid and b.get("status") == "active"]
    if not bks:
        await update.message.reply_text("У вас нет активных броней. Хотите забронировать? 🏡")
        return
    for b in bks:
        svc = ""
        for s in b.get("services", []):
            svc += f" {SERVICES[s]['icon']}"
        t = (
            f"✅ <b>Бронь #{b['id']}</b>\n\n"
            f"🏡 {b['house']}{svc}\n"
            f"📅 {b['check_in']} — {b['check_out']} ({b['nights']} н.)\n"
            f"💰 <b>{b['total']}₽</b>\n"
            f"👤 {b['guest_name']} | {b['guest_phone']}"
        )
        await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=book_actions_ikb(b["id"]))

async def cancel_book(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    bid = int(q.data.replace("cl_", ""))
    bks = load_bookings()
    booking = next((b for b in bks if b["id"] == bid), None)
    upd_booking(bid, {"status": "cancelled"})
    await q.edit_message_text(f"❌ Бронь #{bid} отменена.")
    if ADMIN_CHAT_ID and booking:
        txt = (
            f"❌ <b>Бронь #{bid} отменена гостем</b>\n\n"
            f"🏡 {booking['house']}\n"
            f"👤 {booking.get('guest_name', '—')} | {booking.get('guest_phone', '—')}\n"
            f"📅 {booking.get('check_in', '—')} — {booking.get('check_out', '—')}\n"
            f"💰 {booking.get('total', '—')}₽"
        )
        try:
            await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=txt, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Admin notify cancel: {e}")

async def admin_about(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data["adm_bid"] = q.data.replace("adm_", "")
    await q.edit_message_text(
        f"📝 Напишите сообщение администратору.\n"
        f"Он ответит вам в ближайшее время.", reply_markup=cancel_kb())
    return ADMIN_MSG

async def admin_send_msg(update: Update, ctx):
    if not ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Администратор не подключён.")
        return ConversationHandler.END
    u = update.effective_user
    bid = ctx.user_data.get("adm_bid", "")
    txt = f"💬 <b>Сообщение от гостя</b>\n\n👤 {u.full_name} (@{u.username or 'нет'})\n🆔 {u.id}"
    if bid:
        txt += f"\n🗂 По брони #{bid}"
    txt += f"\n\n{update.message.text}"
    await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=txt, parse_mode=ParseMode.HTML)
    await update.message.reply_text("✅ Отправлено! Администратор ответит вам.", reply_markup=main_kb())
    return ConversationHandler.END

# ── Бронирование ───────────────────────────────────────────────────

async def book_start(update: Update, ctx):
    ctx.user_data.clear()
    await update.message.reply_text("🏡 Выберите домик:", reply_markup=houses_ikb())
    return SEL_HOUSE

async def book_from_house(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    ctx.user_data["house"] = q.data.replace("h_", "")
    h = HOUSES[ctx.user_data["house"]]
    await q.edit_message_text(
        f"{h['icon']} <b>{h['name']}</b>\n{h['price']}₽/сутки\n\n"
        "📅 Выберите дату <b>заезда</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=calendar_kb(date.today().year, date.today().month, "ci"))
    return SEL_CHECKIN

async def sel_house(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        await q.edit_message_text("❌ Отменено."); return ConversationHandler.END
    ctx.user_data["house"] = q.data.replace("h_", "")
    h = HOUSES[ctx.user_data["house"]]
    await q.edit_message_text(
        f"{h['icon']} <b>{h['name']}</b>\n{h['price']}₽/сутки\n\n"
        "📅 Выберите дату <b>заезда</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=calendar_kb(date.today().year, date.today().month, "ci"))
    return SEL_CHECKIN

async def cal_handler(update: Update, ctx, prefix):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        await q.edit_message_text("❌ Отменено.")
        return ConversationHandler.END
    parts = q.data.split("_")
    if parts[0] == "cal":
        _, pfx, y, m = parts
        await q.edit_message_text(
            "📅 Выберите дату:",
            reply_markup=calendar_kb(int(y), int(m), pfx))
        return None
    dt_str = parts[-1]
    dt = date.fromisoformat(dt_str)
    if prefix == "ci":
        ctx.user_data["ci"] = dt_str
        ctx.user_data["ci_date"] = dt
        h = HOUSES[ctx.user_data["house"]]
        await q.edit_message_text(
            f"✅ Заезд: {dt_str}\n\n"
            f"📅 Теперь выберите дату <b>выезда</b>:",
            parse_mode=ParseMode.HTML,
            reply_markup=calendar_kb(dt.year, dt.month, "co"))
        return SEL_CHECKOUT
    else:
        ci = ctx.user_data["ci_date"]
        if dt <= ci:
            await q.answer("Дата выезда должна быть позже даты заезда!", show_alert=True)
            return None
        ctx.user_data["co"] = dt_str
        nights = (dt - ci).days
        ctx.user_data["nights"] = nights
        h = HOUSES[ctx.user_data["house"]]
        total = sum(h["wd_price"] if is_wd(ci + timedelta(days=i)) else h["price"] for i in range(nights))
        ctx.user_data["base"] = total
        await q.edit_message_text(
            f"📅 {ctx.user_data['ci']} — {dt_str} ({nights} н.)\n💰 Базовая стоимость: {total}₽\n\n"
            "🛁 <b>Дополнительные услуги:</b>\n"
            "Выберите нужные (можно несколько):",
            parse_mode=ParseMode.HTML,
            reply_markup=services_ikb(ctx.user_data.get("svcs", [])))
        return SEL_SERVICES

async def sel_checkin(update: Update, ctx):
    return await cal_handler(update, ctx, "ci")

async def sel_checkout(update: Update, ctx):
    return await cal_handler(update, ctx, "co")

async def sel_services(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "cancel":
        await q.edit_message_text("❌ Отменено."); return ConversationHandler.END
    if d == "sv_done":
        svcs = ctx.user_data.get("svcs", [])
        svc_total = sum(SERVICES[s]["price"] for s in svcs)
        total = ctx.user_data["base"] + svc_total
        ctx.user_data["total"] = total
        ctx.user_data["svcs"] = svcs
        h = HOUSES[ctx.user_data["house"]]
        svc_line = ""
        if svcs:
            svc_line = "\n🛁 Услуги: " + ", ".join(f"{SERVICES[s]['icon']} {SERVICES[s]['name']} (+{SERVICES[s]['price']}₽)" for s in svcs)
        await q.edit_message_text(
            f"📋 <b>Проверьте бронь:</b>\n\n"
            f"{h['icon']} <b>{h['name']}</b>\n"
            f"📅 {ctx.user_data['ci']} — {ctx.user_data['co']} ({ctx.user_data['nights']} н.)"
            f"{svc_line}\n"
            f"💰 <b>Итого: {total}₽</b>\n\n"
            f"Всё верно?",
            parse_mode=ParseMode.HTML, reply_markup=confirm_ikb())
        return CONFIRM
    svc_key = d.replace("sv_", "")
    svcs = ctx.user_data.get("svcs", [])
    if svc_key in svcs:
        svcs.remove(svc_key)
    else:
        svcs.append(svc_key)
    ctx.user_data["svcs"] = svcs
    await q.edit_message_reply_markup(reply_markup=services_ikb(svcs))
    return SEL_SERVICES

async def confirm(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        await q.edit_message_text("❌ Отменено."); return ConversationHandler.END
    if q.data == "cnf_restart":
        ctx.user_data.clear()
        await q.edit_message_text("🏡 Выберите домик:", reply_markup=houses_ikb())
        return SEL_HOUSE
    await q.edit_message_text("✅ Как к вам обращаться?")
    return NAME

async def get_name(update: Update, ctx):
    ctx.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📱 Ваш номер телефона:", reply_markup=cancel_kb())
    return PHONE

async def get_phone(update: Update, ctx):
    ctx.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("💬 Пожелания? (отправьте `/skip` или напишите)", parse_mode=ParseMode.HTML)
    return COMMENT

async def get_comment(update: Update, ctx):
    ctx.user_data["comment"] = update.message.text.strip()
    return await finish(update, ctx)

async def skip_comment(update: Update, ctx):
    ctx.user_data["comment"] = ""
    return await finish(update, ctx)

async def finish(update: Update, ctx):
    h = HOUSES[ctx.user_data["house"]]
    data = {
        "house": h["name"],
        "check_in": ctx.user_data["ci"],
        "check_out": ctx.user_data["co"],
        "nights": ctx.user_data["nights"],
        "services": ctx.user_data.get("svcs", []),
        "total": ctx.user_data["total"],
        "guest_name": ctx.user_data["name"],
        "guest_phone": ctx.user_data["phone"],
        "guest_comment": ctx.user_data.get("comment", ""),
        "user_id": update.effective_user.id,
    }
    bid = save_booking(data)

    svc_line = ""
    for s in data["services"]:
        svc_line += f" {SERVICES[s]['icon']}"

    await update.message.reply_text(
        f"✅ <b>Бронь #{bid} подтверждена!</b>{svc_line}\n\n"
        f"🏡 {data['house']}\n"
        f"📅 {data['check_in']} — {data['check_out']}\n"
        f"💰 <b>{data['total']}₽</b>\n\n"
        f"📞 Вопросы: {ADMIN_PHONE}\n"
        f"📩 {ADMIN_USERNAME}\n\n"
        f"Хорошего отдыха! 🌲",
        parse_mode=ParseMode.HTML, reply_markup=main_kb())

    if ADMIN_CHAT_ID:
        s_txt = " ".join(SERVICES[s]["icon"] for s in data["services"]) if data["services"] else "—"
        txt = (
            f"🔔 <b>Новая бронь #{bid}</b>\n\n"
            f"🏡 {data['house']}\n"
            f"👤 {data['guest_name']} | {data['guest_phone']}\n"
            f"📅 {data['check_in']} — {data['check_out']}\n"
            f"🌙 {data['nights']} н.\n"
            f"🛠 Услуги: {s_txt}\n"
            f"💰 {data['total']}₽\n"
        )
        if data["guest_comment"]:
            txt += f"💬 {data['guest_comment']}"
        try:
            await ctx.bot.send_message(chat_id=ADMIN_CHAT_ID, text=txt, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Admin notify: {e}")

    ctx.user_data.clear()
    return ConversationHandler.END

async def book_cancel(update: Update, ctx):
    await update.message.reply_text("❌ Отменено.", reply_markup=main_kb())
    return ConversationHandler.END

# ── Связь с админом (из меню) ─────────────────────────────────────

async def admin_connect_menu(update: Update, ctx):
    ctx.user_data.clear()
    await update.message.reply_text(
        "📝 Напишите сообщение администратору.\nОн ответит вам лично.", reply_markup=cancel_kb())
    return ADMIN_MSG

async def admin_msg_cancel(update: Update, ctx):
    await update.message.reply_text("❌ Отменено.", reply_markup=main_kb())
    return ConversationHandler.END

# ── Админ команды ──────────────────────────────────────────────────

async def admin_bookings(update: Update, ctx):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    bks = load_bookings()
    if not bks:
        await update.message.reply_text("Нет заявок.")
        return
    t = "📋 <b>Все заявки:</b>\n\n"
    for b in reversed(bks[-30:]):
        st = "✅" if b.get("status") == "active" else "❌"
        t += f"{st} <b>#{b['id']}</b> — {b['house']}\n"
        t += f"   {b['guest_name']} | {b['guest_phone']}\n"
        t += f"   {b['check_in']}—{b['check_out']} | {b['total']}₽\n"
        t += f"   🕐 {b.get('created_at','')[:16]}\n\n"
    await update.message.reply_text(t, parse_mode=ParseMode.HTML)

async def admin_reply(update: Update, ctx):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    txt = update.message.text
    parts = txt.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text("Формат: /reply <user_id> <текст>")
        return
    try:
        uid = int(parts[1])
        reply = parts[2]
        await ctx.bot.send_message(
            chat_id=uid,
            text=f"📩 <b>Ответ от администратора:</b>\n\n{reply}",
            parse_mode=ParseMode.HTML)
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {uid}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ── Текстовые кнопки ──────────────────────────────────────────────

async def text_handler(update: Update, ctx):
    m = {"🏡 Домики": houses_cmd, "📅 Бронь": book_start,
         "📋 Мои брони": my_bookings, "❓ FAQ": faq_cmd,
         "📞 Связь с админом": admin_connect_menu, "📱 Контакты": contacts_cmd}
    if update.message.text in m:
        await m[update.message.text](update, ctx)
    else:
        await update.message.reply_text("Используйте кнопки меню 👇", reply_markup=main_kb())

# ── Запуск ─────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setadmin", set_admin))
    app.add_handler(CommandHandler("bookings", admin_bookings))
    app.add_handler(CommandHandler("reply", admin_reply))
    app.add_handler(CallbackQueryHandler(cancel_book, pattern=r"^cl_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_about, pattern=r"^adm_\d+$"))

    book_conv = ConversationHandler(
        entry_points=[CommandHandler("book", book_start),
                      MessageHandler(filters.Regex("^📅 Бронь$"), book_start),
                      CallbackQueryHandler(book_from_house, pattern=r"^h_")],
        states={
            SEL_HOUSE: [CallbackQueryHandler(sel_house)],
            SEL_CHECKIN: [CallbackQueryHandler(sel_checkin, pattern=r"^(ci_|cal_ci_|cancel)")],
            SEL_CHECKOUT: [CallbackQueryHandler(sel_checkout, pattern=r"^(co_|cal_co_|cancel)")],
            SEL_SERVICES: [CallbackQueryHandler(sel_services)],
            CONFIRM: [CallbackQueryHandler(confirm)],
            NAME: [
                MessageHandler(filters.Regex("^❌ Отмена$"), book_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            PHONE: [
                MessageHandler(filters.Regex("^❌ Отмена$"), book_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            COMMENT: [
                MessageHandler(filters.Regex("^❌ Отмена$"), book_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment),
                CommandHandler("skip", skip_comment),
            ],
        },
        fallbacks=[CommandHandler("cancel", book_cancel)],
        per_message=False,
    )
    app.add_handler(book_conv)

    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📞 Связь с админом$"), admin_connect_menu),
            CallbackQueryHandler(admin_about, pattern=r"^adm_\d+$"),
        ],
        states={
            ADMIN_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_msg),
                MessageHandler(filters.Regex("^❌ Отмена$"), admin_msg_cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_msg_cancel)],
        per_message=False,
    )
    app.add_handler(admin_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

# پنل تنظیمات تعاملی — /settings
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import settings as cfg
from .persian import fa_digits


def _onoff(v: bool) -> str:
    return "✅ فعال" if v else "❌ غیرفعال"


def main_menu() -> InlineKeyboardMarkup:
    auto = cfg.get("auto_enabled")
    channel = cfg.get("channel") or "—"
    rows = [
        [InlineKeyboardButton(
            f"{'🔴' if auto else '🟢'} حالت خودکار: {_onoff(auto)}",
            callback_data="set:auto_toggle",
        )],
        [InlineKeyboardButton(
            f"📡 نام کانال: {channel}",
            callback_data="ask:channel",
        )],
        [InlineKeyboardButton(
            f"➖ کسر خرید: {cfg.get('buy_deduction'):,} تومان",
            callback_data="ask:deduction",
        )],
        [
            InlineKeyboardButton("👤 ادمین‌ها", callback_data="menu:admins"),
            InlineKeyboardButton("🔔 گزارش دوره‌ای", callback_data="toggle:reports"),
        ],
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="settings:refresh")],
    ]
    return InlineKeyboardMarkup(rows)


def settings_text() -> str:
    admins = cfg.get_admins()
    lines = [
        "<b>⚙️ تنظیمات ربات</b>",
        "",
        f"🟢 حالت خودکار: <b>{_onoff(cfg.get('auto_enabled'))}</b>",
        f"📡 کانال انتشار: <b>{escape(str(cfg.get('channel') or '—'))}</b>",
        f"➖ کسر خرید: <b>{cfg.get('buy_deduction'):,} تومان</b> "
        "(خرید = فروش − همین عدد)",
        "ℹ️ رفتار خودکار: هر دقیقه فقط «فروش» از کانال مرجع چک می‌شود؛ "
        "با تغییرش پست جدید می‌رود. ساعات انتشار: ۹:۳۰ تا ۲۰:۰۰.",
        f"🔔 گزارش دوره‌ای ادمین: {_onoff(cfg.get('reports_enabled'))}",
        f"👤 ادمین‌ها: {', '.join(fa_digits(a) for a in admins) or '—'}",
    ]
    return "\n".join(lines)


def back_btn() -> InlineKeyboardButton:
    return InlineKeyboardButton("🔙 بازگشت", callback_data="settings:home")


def admins_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن ادمین", callback_data="ask:addadmin")],
        [InlineKeyboardButton("➖ حذف ادمین", callback_data="ask:deladmin")],
        [back_btn()],
    ])


async def show(update_or_query, _context: ContextTypes.DEFAULT_TYPE):
    """نمایش/بروزرسانی پنل — هم از دستور، هم از کلیک دکمه"""
    q = update_or_query.callback_query
    if q is not None:
        await q.answer()
        await q.edit_message_text(settings_text(), parse_mode=ParseMode.HTML,
                                  reply_markup=main_menu())
    else:
        await update_or_query.effective_message.reply_text(
            settings_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """روتر دکمه‌های پنل"""
    from .bot import is_admin   # ایمپورت داخلی برای جلوگیری از چرخه

    query = update.callback_query
    data = query.data or ""

    if not is_admin(update):
        await query.answer("فقط ادمین به تنظیمات دسترسی دارد.", show_alert=True)
        return

    # ── ناوبری ──
    if data == "settings:home":
        await show(update, context)
        return
    if data == "settings:refresh":
        # بروزرسانی پنل — همان منوی اصلی با مقادیر تازه
        await show(update, context)
        return
    if data == "menu:admins":
        await query.answer()
        await query.edit_message_text(
            "<b>👤 مدیریت ادمین‌ها</b>\n\nادمین‌ها: "
            + ", ".join(fa_digits(a) for a in cfg.get_admins()),
            parse_mode=ParseMode.HTML,
            reply_markup=admins_menu(),
        )
        return
    # ── تغییر وضعیت‌ها ──
    if data == "set:auto_toggle":
        cfg.update("auto_enabled", not cfg.get("auto_enabled"))
        await show(update, context)
        return
    if data == "toggle:reports":
        cfg.update("reports_enabled", not cfg.get("reports_enabled"))
        await show(update, context)
        return

    # ── شروع ورودی متنی (کانال / افزودن-حذف ادمین) ──
    if data in ("ask:channel", "ask:deduction", "ask:addadmin", "ask:deladmin"):
        await query.answer()
        prompts = {
            "ask:channel": ("نام کاربری کانال را بفرست (مثل @my_channel یا عدد -100...)",
                            "wait:channel"),
            "ask:deduction": (
                "مبلغ کسر خرید را به **تومان** بفرست (فقط عدد، بدون جداکننده).\n"
                "مثلاً: 100000 یعنی خرید = فروش − ۱۰۰ هزار تومان",
                "wait:deduction",
            ),
            "ask:addadmin": ("آی‌دی عددی ادمین جدید را بفرست:", "wait:addadmin"),
            "ask:deladmin": ("آی‌دی عددی ادمینی که باید حذف شود را بفرست:", "wait:deladmin"),
        }
        text, wait_state = prompts[data]
        context.user_data["await_input"] = wait_state
        # PTB 22.x: message می‌تواند None باشد (پیام خیلی قدیمی) → جایگزین امن
        target_msg = query.message or query.effective_message
        if target_msg is not None:
            await target_msg.reply_text(f"{text}\n\n(/cancel برای انصراف)")
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{text}\n\n(/cancel برای انصراف)",
            )
        return


async def handle_wait_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت ورودی متنی که پنل منتظرش است"""
    state = context.user_data.get("await_input")
    if not state:
        return
    text = (update.message.text or "").strip()
    context.user_data["await_input"] = None

    if state == "wait:channel":
        # همان کاری که قبلاً /setchannel می‌کرد: پذیرش @username یا آی‌دی عددی
        value = text
        if not (value.startswith("@") or value.lstrip("-").isdigit()):
            await update.effective_message.reply_text(
                "❌ فرمت درست نیست.\n"
                "مثل <code>@my_channel</code> بفرست یا آی‌دی عددی کانال "
                "(شکل <code>-100...</code>) را بفرست.",
                parse_mode=ParseMode.HTML,
            )
            context.user_data["await_input"] = "wait:channel"  # دوباره منتظر ورودی بمان
            return
        from . import database as dbmod
        dbmod.save_state("post_channel", {"value": value})
        cfg.update("channel", value)
        await update.effective_message.reply_text(
            f"✅ کانال انتشار روی {escape(value)} ثبت شد.\n"
            "یادت باشد ربات باید در آن کانال ادمین باشد تا بتواند پست بفرستد.\n"
            "برای تست همین حالا /publish را بزن."
        )
    elif state == "wait:deduction":
        # کسر خرید — کاملاً دستی و آزاد: هر عدد تومانی که ادمین بفرستد
        cleaned = text.replace(",", "").replace("٬", "").strip()
        if not cleaned.isdigit():
            await update.effective_message.reply_text(
                "❌ فقط عدد به تومان بفرست؛ مثلاً: 100000"
            )
            context.user_data["await_input"] = "wait:deduction"  # منتظر ورودی درست بمان
            return
        value = int(cleaned)
        cfg.update("buy_deduction", value)
        await update.effective_message.reply_text(
            f"✅ کسر خرید روی {value:,} تومان ثبت شد.\n"
            "از این به بعد: قیمت خرید = قیمت فروش − همین عدد."
        )
    elif state == "wait:addadmin":
        try:
            admin_id = int(text)
        except ValueError:
            await update.effective_message.reply_text("❌ آی‌دی باید عدد باشد؛ مثلا 306652923")
            return
        admins = cfg.get_admins()
        if admin_id in admins:
            await update.effective_message.reply_text("این آی‌دی از قبل ادمین است.")
        else:
            admins.append(admin_id)
            cfg.update("admins", admins)
            await update.effective_message.reply_text(f"✅ ادمین {fa_digits(admin_id)} افزوده شد.")
    elif state == "wait:deladmin":
        try:
            admin_id = int(text)
        except ValueError:
            await update.effective_message.reply_text("❌ آی‌دی باید عدد باشد.")
            return
        admins = cfg.get_admins()
        if admin_id not in admins:
            await update.effective_message.reply_text("این آی‌دی در لیست ادمین‌ها نیست.")
        elif len(admins) <= 1:
            await update.effective_message.reply_text("حداقل یک ادمین باید بماند!")
        else:
            admins.remove(admin_id)
            cfg.update("admins", admins)
            await update.effective_message.reply_text(f"➖ ادمین {fa_digits(admin_id)} حذف شد.")

    await show(update, context)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["await_input"] = None
    await update.effective_message.reply_text("انصراف داده شد.")

// ═════════════════════════════════════════════════════════════════════════════
// GOLD PRICE BOT — SINGLE-FILE CLOUDFLARE WORKER
// Merged from the modular sources so it can be pasted as-is into the
// Cloudflare dashboard editor. Python counterpart: bot/ (local PTB edition).
//
// PRICING MODEL (Ali's decision, Aug 2026):
//   • Only the SELL price is scraped from the reference channel (@MARKIZ_ARG)
//     and converted Rial → Toman (÷10).
//   • BUY is COMPUTED locally:  buy = sell − buy_deduction  (default 100,000
//     Toman; editable ONLY manually via panel/KV — free-form number).
//   • All displayed prices use ENGLISH digits + "تومان" unit.
//   • Channel posts carry TWO buttons: right "🔴 فروش به ما", left "🟢 خرید از ما"
//     (both deep-link to the bot; no callback yet).
//   • Auto-publish works ONLY inside business hours 09:30–20:00 Tehran time.
//
//   • scheduled (cron every minute): scrape reference channel → KV +
//     instant change alert to admins + auto-publish on SELL change (in hours)
//   • fetch (Telegram webhook): /now /status /publish /start /help
//
// Environment variables (Dashboard → Settings → Variables):
//   BOT_TOKEN      bot token from @BotFather          [required]
//   ADMIN_IDS      comma-separated admin IDs          [required]
//   SECRET_TOKEN   random webhook secret (optional but recommended)
// KV binding:  STATE   (namespace e.g. gold-bot-state) — key "state":
//   { prices:{sell:{value,msg_id,time}}, settings:{auto_enabled,channel,
//     buy_deduction}, last_post:{jalali,buy,sell} }
// Cron:        * * * * *   (every minute — free plan allows up to 5 triggers)
//
// NOTE: bot-facing message texts stay Persian by design; comments/logs English.
// ═════════════════════════════════════════════════════════════════════════════

const SOURCE_CHANNEL = "MARKIZ_ARG";
const DEFAULT_BUY_DEDUCTION_TOMAN = 100_000; // manual-editable via panel/KV
const WORK_START_MIN = 9 * 60 + 30; // 09:30 Tehran
const WORK_END_MIN = 20 * 60;       // 20:00 Tehran

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 1 — Persian/Jalali helpers. Port of bot/persian.py + bot/jalali.py.
// Prices intentionally use ENGLISH digits; Persian digits remain only for the
// Jalali date and reference message id.
// ─────────────────────────────────────────────────────────────────────────────

const FA_MAP = { "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
                 "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹",
                 ",": "٬", ".": "٫", "%": "٪" };

/** Used for dates/ids only — NOT for prices */
export function faDigits(value) {
  return String(value).replace(/[0-9,.%]/g, (ch) => FA_MAP[ch]);
}

/** Price formatting: thousands separator + ENGLISH digits (unit added by caller):
 *  95340000 → "95,340,000" */
export function money(amount) {
  return Number(amount).toLocaleString("en-US");
}

// ── Jalali calendar ──────────────────────────────────────────────────────────
// Standard jdf algorithm — port of bot/jalali.py
const G_MONTH_DAYS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

const J_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

// getDay(): Sunday=0 … Saturday=6  ←→  Persian order starts at Monday
const J_WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"];

export function gregorianToJalali(gy, gm, gd) {
  let days;
  const gy2 = gm > 2 ? gy + 1 : gy;
  days =
    355666 + 365 * gy +
    Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) +
    gd + G_MONTH_DAYS[gm - 1];
  let jy = -1595 + 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  let jm, jd;
  if (days < 186) {
    jm = 1 + Math.floor(days / 31);
    jd = 1 + (days % 31);
  } else {
    jm = 7 + Math.floor((days - 186) / 30);
    jd = 1 + ((days - 186) % 30);
  }
  return [jy, jm, jd];
}

export const TEHRAN_OFFSET_MIN = 210; // UTC+3:30 (Iran abolished DST)

/** Date (any moment) + Tehran offset (minutes) → "سه‌شنبه ۳ شهریور ۱۴۰۵ • ۲۰:۰۴" */
export function formatJalaliTehran(dateUtc, tehranOffsetMin = TEHRAN_OFFSET_MIN) {
  const t = new Date(dateUtc.getTime() + tehranOffsetMin * 60_000);
  const [jy, jm, jd] = gregorianToJalali(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
  const wd = J_WEEKDAYS[(t.getUTCDay() + 6) % 7]; // JS Sunday=0 → index 6
  const hh = String(t.getUTCHours()).padStart(2, "0");
  const mm = String(t.getUTCMinutes()).padStart(2, "0");
  return `${wd} ${faDigits(jd)} ${J_MONTHS[jm - 1]} ${faDigits(jy)} • ${faDigits(`${hh}:${mm}`)}`;
}

/** Minutes since midnight in Tehran for a given UTC moment */
export function tehranMinutesOfDay(dateUtc, offsetMin = TEHRAN_OFFSET_MIN) {
  const t = new Date(dateUtc.getTime() + offsetMin * 60_000);
  return t.getUTCHours() * 60 + t.getUTCMinutes();
}

export function withinWorkingHours(dateUtc) {
  const m = tehranMinutesOfDay(dateUtc);
  return WORK_START_MIN <= m && m < WORK_END_MIN;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 2 — Scrape the reference channel via its public web preview
// t.me/s/<channel>. Port of bot/scraper.py. SELL-ONLY per the pricing model;
// the channel quotes Rial → converted to Toman (÷10) right here.
// ─────────────────────────────────────────────────────────────────────────────

const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
};

const RE_MSG_TEXT = /tgme_widget_message_text[^>]*>([\s\S]*?)<\/div>/g;
const RE_TIME = /<time datetime="([^"]+)"/g;
const RE_ID = /data-post="[^\/]*\/(\d+)"/g;

// Sample message text: «🔴 قیمت فروش آبشده نقد فردا: \n\n954٬000٬000 ریال»
const RE_SELL = /قیمت\s+فروش\s+آبشده[^\n:]*:\s*\n?\s*([\d۰-۹.,٬\s]+?)\s*ریال/;

/** "۹۵۲٬۱۰۰٬۰۰۰" or "952,100,000" → 952100000 */
export function toInt(raw) {
  const s = String(raw)
    .replace(/[۰-۹]/g, (ch) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(ch)))
    .replace(/[.,\s٬]/g, "");
  return /^\d+$/.test(s) ? parseInt(s, 10) : null;
}

/** If the message carries a SELL price → { kind:'sell', value(Toman) }, else null.
 *  Buy is never scraped anymore — it is computed in the bot. */
export function parseMessage(text) {
  const m = text.match(RE_SELL);
  if (m) {
    const vRial = toInt(m[1]);
    if (vRial) return { kind: "sell", value: Math.floor(vRial / 10) }; // Rial → Toman
  }
  return null;
}

function cleanHtml(fragment) {
  return fragment
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#039;/g, "'").replace(/&amp;/g, "&")
    .trim();
}

function extractMessages(html) {
  const texts = [...html.matchAll(RE_MSG_TEXT)].map((m) => cleanHtml(m[1]));
  const times = [...html.matchAll(RE_TIME)].map((m) => m[1]);
  const ids = [...html.matchAll(RE_ID)].map((m) => m[1]);

  const out = [];
  for (let i = 0; i < texts.length; i++) {
    const idStr = ids[i] ?? "0";
    out.push({
      id: /^\d+$/.test(idStr) ? parseInt(idStr, 10) : 0,
      timeIso: times[i] ?? "",
      text: texts[i],
    });
  }
  out.sort((a, b) => a.id - b.id);
  return out;
}

/** Latest sell across the page's messages — mirrors extract_latest in bot.py */
export function extractLatest(messages) {
  const result = {};
  for (const msg of messages) {
    const parsed = parseMessage(msg.text);
    if (!parsed) continue;
    const prev = result[parsed.kind];
    if (!prev || msg.id >= prev.msg_id) {
      result[parsed.kind] = { value: parsed.value, msg_id: msg.id, time: msg.timeIso };
    }
  }
  return result;
}

/** Fetch and parse the channel page; returns null on any failure */
export async function fetchLatest(channel) {
  const resp = await fetch(`https://t.me/s/${channel}`, { headers: HEADERS });
  if (!resp.ok) {
    console.log(`failed to fetch t.me/s/${channel}: HTTP ${resp.status}`);
    return null;
  }
  const html = await resp.text();
  const messages = extractMessages(html);
  if (messages.length === 0) return null;
  const latest = extractLatest(messages);
  if (Object.keys(latest).length === 0) return null;
  return latest;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 3 — Message formatting (HTML parse mode, RTL layout).
// Mirrors bot/formatting.py. Unit: تومان · digits: English.
// Formatting functions take `deduction` (= buy_deduction) explicitly so they
// stay pure; Section 4 resolves it from KV state.
// ─────────────────────────────────────────────────────────────────────────────

export const SOURCE_LINK = "https://t.me/MARKIZ_ARG";
const ZWNJ = "\u200c"; // zero-width non-joiner
const RLM = "\u202b"; // begin right-to-left embedding
const PDF = "\u202c"; // pop directional formatting (end RTL block)

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function computedBuy(sellToman, deduction) {
  if (sellToman == null) return null;
  return sellToman - (deduction ?? DEFAULT_BUY_DEDUCTION_TOMAN);
}

function priceLine(label, emoji, valueToman) {
  if (valueToman == null) return `${emoji} ${label}: —`;
  // RLM…PDF wraps the number so "95,340,000 تومان" renders correctly in RTL
  return `${emoji} ${label}: ${RLM}${money(valueToman)} تومان${PDF}`;
}

function jalaliNow() {
  return formatJalaliTehran(new Date(), TEHRAN_OFFSET_MIN);
}

/** Full report for admins (mirrors admin_report) */
export function adminReport(latest, deduction) {
  const sellV = latest.sell?.value ?? null;
  const buyV = computedBuy(sellV, deduction);
  const lines = [
    "<b>📊 گزارش لحظه‌ای طلا (آبشده ۹۹۹)</b>",
    "",
    priceLine("خرید", "🔵", buyV),
    priceLine("فروش", "🔴", sellV),
  ];
  if (buyV != null && sellV != null) {
    lines.push(`⚪️ اختلاف خرید/فروش: ${RLM}${money(sellV - buyV)} تومان${PDF}`);
  }
  lines.push("", `🕒 ${escapeHtml(jalaliNow())}`);
  if (latest.sell?.msg_id) lines.push(`🆔 پیام مرجع: ${faDigits(latest.sell.msg_id)}`);
  lines.push(`📡 منبع: ${escapeHtml(SOURCE_LINK)}`);
  return lines.join("\n");
}

/** Sell-change alert (mirrors change_alert) — includes the computed buy */
export function changeAlert(kind, newValue, oldValue, deduction) {
  const diff = newValue - oldValue;
  const arrow = diff > 0 ? "⬆️" : "⬇️";
  const sign = diff > 0 ? "+" : "−";
  const newBuy = computedBuy(newValue, deduction);
  const oldBuy = computedBuy(oldValue, deduction);
  return [
    `${arrow} <b>تغییر قیمت فروش آبشده</b>`,
    "",
    priceLine("جدید", "🔴", newValue),
    `▫️ قبلی: ${RLM}${money(oldValue)} تومان${PDF}`,
    `▫️ تغییر: ${RLM}${sign}${money(Math.abs(diff))} تومان${PDF}`,
    "",
    priceLine("خرید (محاسبه‌ای)", "🔵", newBuy),
    `▫️ قبلی: ${RLM}${oldBuy != null ? money(oldBuy) : "—"} تومان${PDF}`,
    "",
    `🕒 ${escapeHtml(jalaliNow())}`,
  ].join("\n");
}

/** Channel post — exactly the previous layout; buy is computed from sell */
export function publishPost(latest, deduction) {
  const sellV = latest.sell?.value ?? null;
  const buyV = computedBuy(sellV, deduction);
  return [
    "💠 <b>قیمت لحظه‌ای طلای آبشده</b> 💠",
    "",
    priceLine("خرید", "🔵", buyV),
    priceLine("فروش", "🔴", sellV),
    "",
    `🕒 ${escapeHtml(jalaliNow())}`,
  ].join("\n");
}

/** Two buttons under channel posts: first button sits on the RIGHT in Telegram's
 *  RTL rendering → "فروش به ما" right, "خرید از ما" left. Both deep-link to the bot. */
export function contactKeyboard(botUsername) {
  const url = botUsername ? `https://t.me/${botUsername}` : SOURCE_LINK;
  return {
    inline_keyboard: [[
      { text: "🔴 فروش به ما", url },
      { text: "🟢 خرید از ما", url },
    ]],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 4 — Worker core. Mirrors bot/bot.py for the Cloudflare runtime.
// ─────────────────────────────────────────────────────────────────────────────

function adminIds(env) {
  return String(env.ADMIN_IDS || "").split(",").map((s) => parseInt(s.trim(), 10)).filter(Number.isFinite);
}

function api(method, token, body) {
  return fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function sendMessage(env, chatId, text, extra = {}) {
  const resp = await api("sendMessage", env.BOT_TOKEN, {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    ...extra,
  });
  if (!resp.ok) console.log(`sendMessage to ${chatId} failed: ${await resp.text()}`);
  return resp.ok;
}

async function getState(env) {
  const raw = await env.STATE.get("state", "json");
  return raw ?? { prices: {}, settings: {}, last_post: {} };
}

async function saveState(env, state) {
  // KV free tier allows only 1,000 writes/day — we write ONLY when the sell
  // price actually changed, keeping usage around ~100–300 writes per day.
  await env.STATE.put("state", JSON.stringify(state));
}

/** Buy deduction from KV settings; falls back to the built-in default */
function buyDeductionOf(state) {
  const v = state.settings?.buy_deduction;
  return Number.isFinite(v) ? v : DEFAULT_BUY_DEDUCTION_TOMAN;
}

/** One scrape attempt; null on error */
async function collectOnce(env) {
  try {
    return await fetchLatest(SOURCE_CHANNEL);
  } catch (exc) {
    console.log(`channel scrape failed: ${exc}`);
    return null;
  }
}

// ── Auto-publish: check every minute → post on SELL change, in work hours ────
async function maybeAutoPublish(env, latest, nowUtc, changedKinds) {
  const state = await getState(env);
  const cfg = state.settings;
  if (!cfg.auto_enabled) return;
  const target = cfg.channel;
  if (!target) return;

  // Business hours only: 09:30–20:00 Tehran
  if (!withinWorkingHours(nowUtc)) return;

  // Only a real SELL change creates a post (buy is derived — no spam)
  if (!changedKinds.has("sell")) return;

  const me = await api("getMe", env.BOT_TOKEN, {});
  let username = null;
  if (me.ok) username = (await me.json()).result.username;
  const keyboard = contactKeyboard(username);
  const text = publishPost(latest, buyDeductionOf(state));

  const ok = await sendMessage(env, target, text, { reply_markup: keyboard });
  if (ok) {
    state.last_post = {
      jalali: formatJalaliTehran(nowUtc, TEHRAN_OFFSET_MIN),
      buy: computedBuy(latest.sell?.value ?? null, buyDeductionOf(state)),
      sell: latest.sell?.value ?? null,
    };
    await saveState(env, state); // KV write only on real changes
  }
}

// ── Cron job, runs every minute (mirrors poll_job) ───────────────────────────
export async function scheduled(event, env, ctx) {
  const nowUtc = new Date();
  const latest = await collectOnce(env);
  if (!latest) return;

  const state = await getState(env);
  const old = state.prices || {};

  // Which kinds changed vs the previous scan? (only "sell" can appear now)
  const hadOld = Object.keys(old).length > 0;
  const changedKinds = new Set(
    Object.keys(latest).filter((k) => old[k] && old[k].value !== latest[k].value)
  );

  state.prices = latest;
  // ⚠️ Free-tier KV quota is 1,000 writes/day — write only when the price changed
  if (!hadOld || changedKinds.size > 0) {
    await saveState(env, state);
  }

  const deduction = buyDeductionOf(state);

  // Instant alert to admins whenever the sell price really changed.
  // (Alerts run around the clock; only CHANNEL posts respect work hours.)
  for (const kind of changedKinds) {
    for (const adminId of adminIds(env)) {
      await sendMessage(env, adminId, changeAlert(kind, latest[kind].value, old[kind].value, deduction));
    }
  }

  await maybeAutoPublish(env, latest, nowUtc, changedKinds);
}

// ── Telegram webhook (simple admin commands) ─────────────────────────────────
async function handleUpdate(update, env) {
  const msg = update.message;
  if (!msg || !msg.text) return;
  const userId = msg.from?.id;
  if (!adminIds(env).includes(userId)) return; // admins only

  const cmd = msg.text.split(/\s+/)[0].split("@")[0];
  const state = await getState(env);
  const deduction = buyDeductionOf(state);

  if (cmd === "/start" || cmd === "/help") {
    await sendMessage(env, userId, [
      "🤖 <b>ربات قیمت طلا (نسخه‌ی کلادفلر)</b>",
      "",
      "/now — دریافت فوری آخرین گزارش قیمت",
      "/status — وضعیت سرویس",
      "/publish — ارسال دستی پست قیمت به کانال انتشار",
      "",
      "⚙️ انتشار خودکار: هر دقیقه فقط «فروش» چک می‌شود؛ با تغییرش پست می‌رود.",
      "🕐 ساعات کاری انتشار: ۹:۳۰ تا ۲۰:۰۰",
      `➖ کسر خرید فعلی: ${money(deduction)} تومان (خرید = فروش − کسر)`,
      "ℹ️ واحد همه‌ی قیمت‌ها تومان است.",
    ].join("\n"));
  } else if (cmd === "/now") {
    const latest = Object.keys(state.prices).length ? state.prices : await collectOnce(env);
    if (!latest) { await sendMessage(env, userId, "❌ دریافت قیمت ناموفق بود؛ بعداً تلاش کن."); return; }
    await sendMessage(env, userId, adminReport(latest, deduction));
  } else if (cmd === "/status") {
    const lastJalali = formatJalaliTehran(new Date(), TEHRAN_OFFSET_MIN);
    const hasPrices = Object.keys(state.prices).length > 0;
    await sendMessage(env, userId, [
      "<b>🩺 وضعیت سرویس</b>",
      "",
      `📡 منبع: @${SOURCE_CHANNEL}`,
      "⏱ بازه‌ی کوئری: هر دقیقه (Cloudflare Cron)",
      "🕐 ساعات کاری انتشار: ۰۹:۳۰ تا ۲۰:۰۰ (تهران)",
      `➖ کسر خرید: ${money(deduction)} تومان`,
      hasPrices ? "✅ آخرین داده ذخیره‌شده موجود است" : "⚠️ هنوز داده‌ای ثبت نشده",
      `🕒 ${lastJalali}`,
    ].join("\n"));
  } else if (cmd === "/publish") {
    const target = state.settings.channel;
    if (!target) {
      await sendMessage(env, userId, "کانال انتشار تنظیم نشده. در داشبورد کلادفلر داخل KV کلید state → settings.channel را بگذار.");
      return;
    }
    const latest = await collectOnce(env);
    if (!latest) { await sendMessage(env, userId, "❌ قیمت تازه نگرفتم؛ پست ارسال نشد."); return; }
    const me = await api("getMe", env.BOT_TOKEN, {});
    const username = me.ok ? (await me.json()).result.username : null;
    const ok = await sendMessage(env, target, publishPost(latest, deduction), { reply_markup: contactKeyboard(username) });
    await sendMessage(env, userId, ok ? `✅ به ${target} ارسال شد.` : "❌ ارسال نشد؛ چک کن ربات ادمین کانال باشد.");
  }
}

export default {
  async fetch(request, env, ctx) {
    // Validate the webhook secret_token header (if configured)
    const secret = env.SECRET_TOKEN;
    if (secret && request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== secret) {
      return new Response("forbidden", { status: 403 });
    }
    let update = null;
    try { update = await request.json(); } catch { /* health ping */ }
    if (update) await handleUpdate(update, env);
    return new Response("ok");
  },

  scheduled,
};

// Verify the merged single-file worker: sell-only scraping → Toman, computed
// buy, English digits + Toman unit, dual buttons. Run:
//   node deploy/cloudflare-worker/test-worker.mjs
import {
  fetchLatest, toInt, parseMessage,
  money, formatJalaliTehran, TEHRAN_OFFSET_MIN, withinWorkingHours,
  adminReport, publishPost, changeAlert, contactKeyboard,
} from "./worker.js";

const DEDUCTION = 100_000; // default buy deduction (Toman)

console.log("── 1) number parsing ──");
console.log(toInt("۹۵۴٬۰۰۰٬۰۰۰"), toInt("954,000,000"));
console.log(money(95340000), "← English digits + thousands separator");

console.log("\n── 2) parseMessage: SELL only, Rial→Toman ──");
console.log(parseMessage("🔴 قیمت فروش آبشده نقد فردا: \n\n954٬000٬000 ریال"),
  "← ۹۵۴٬۰۰۰٬۰۰۰ ریال = 95,400,000 تومان");
console.log(parseMessage("🔵 قیمت خرید آبشده نقد فردا: \n\n952٬100٬000 ریال"),
  "← buy must be null (never scraped)");

console.log("\n── 3) Jalali date + work hours ──");
console.log(formatJalaliTehran(new Date(), TEHRAN_OFFSET_MIN));
const at = (h, m) => { const d = new Date(Date.UTC(2026, 7, 26, 0, m)); d.setUTCHours(h - 3, m - 30 % 60); return d; };
// direct boundary checks via tehranMinutesOfDay math (09:29 / 09:30 / 19:59 / 20:00)
const mkUtc = (tehH, tehM) => new Date(Date.UTC(2026, 7, 26, tehH, tehM) - TEHRAN_OFFSET_MIN * 60_000);
console.log("09:29 →", withinWorkingHours(mkUtc(9, 29)), "| 09:30 →",
  withinWorkingHours(mkUtc(9, 30)), "| 19:59 →", withinWorkingHours(mkUtc(19, 59)),
  "| 20:00 →", withinWorkingHours(mkUtc(20, 0)));
if (withinWorkingHours(mkUtc(9, 29)) || !withinWorkingHours(mkUtc(9, 30))
  || !withinWorkingHours(mkUtc(19, 59)) || withinWorkingHours(mkUtc(20, 0))) {
  throw new Error("work-hours boundaries wrong");
}

console.log("\n── 4) live scrape (sell-only, Toman) ──");
const latest = await fetchLatest("MARKIZ_ARG");
if (!latest || !latest.sell) throw new Error("scrape failed or no sell price");
console.log(JSON.stringify(latest));
const buyComputed = latest.sell.value - DEDUCTION;
console.log(`computed buy = ${money(buyComputed)} تومان (sell − ${money(DEDUCTION)})`);

console.log("\n── 5) messages (Toman unit, English digits, dual buttons) ──");
const rep = adminReport(latest, DEDUCTION);
console.log(rep);
if (!rep.includes("تومان") || rep.includes("ریال")) throw new Error("unit must be تومان");

console.log("----");
const post = publishPost(latest, DEDUCTION);
console.log(post);
if (!post.includes(`${money(latest.sell.value)} تومان`)) throw new Error("sell line wrong");
if (!post.includes(`${money(buyComputed)} تومان`)) throw new Error("computed buy line wrong");

console.log("----");
console.log(changeAlert("sell", latest.sell.value, latest.sell.value - 500_000, DEDUCTION));

console.log("----");
const kb = JSON.stringify(contactKeyboard("yas110gold_bot"));
console.log(kb);
if (!kb.includes("🔴 فروش به ما") || !kb.includes("🟢 خرید از ما")) throw new Error("buttons wrong");

console.log("\n🎉 merged single-file worker verified OK (sell-only + Toman model)");

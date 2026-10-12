import os
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

WATCHLIST_FILE = "watchlist.json"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return {}

def save_watchlist(data):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_dexscreener_data(ca: str):
    url = f"https://api.dexscreener.com/tokens/v1/solana/{ca}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data and len(data) > 0:
            pair = max(data, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
            return pair
        return None
    except Exception as e:
        logger.error(f"DexScreener error: {e}")
        return None

def get_holder_count(ca: str):
    if not BIRDEYE_API_KEY:
        return None
    url = "https://public-api.birdeye.so/defi/token_overview"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    params = {"address": ca}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if data.get("success"):
            return data["data"].get("holder")
        return None
    except:
        return None

def generate_organic_tech_lore(symbol, name, price_change_1h, volume_1h, liquidity, holders, mcap):
    if price_change_1h > 15 and volume_1h > 50000:
        theme = "signal_spike"
    elif holders and holders > 1000 and price_change_1h > 5:
        theme = "network_growth"
    elif liquidity > 30000 and abs(price_change_1h) < 8:
        theme = "accumulation"
    elif price_change_1h < -12:
        theme = "correction"
    else:
        theme = "observation"

    lores = {
        "signal_spike": f"""⚡ **Neural Pulse Detected — ${symbol}**

Di lapisan bawah Solana, sinyal lemah tiba-tiba menguat. Node-node yang sebelumnya diam mulai saling beresonansi. Volume naik tajam, seolah jaringan sedang menguji frekuensi baru.

Ini bukan noise biasa. Ada pola yang mulai terbentuk — organik, belum dipaksa, tapi sudah terasa oleh mereka yang memperhatikan.

*{name}* sedang berbicara dalam bahasa yang hanya dimengerti oleh runner sejati.""",

        "network_growth": f"""🌐 **Node Expansion — ${symbol}**

Jumlah koneksi terus bertambah. Setiap holder baru adalah satu node tambahan dalam jaringan. Distribusi semakin merata, likuiditas menopang, dan sinyal masih bersih.

Proyek ini tidak berteriak. Ia hanya terus tumbuh — pelan, konsisten, seperti protokol yang sedang menemukan product-market-fit-nya sendiri.

Potensi runner muncul saat jaringan mencapai critical mass.""",

        "accumulation": f"""📡 **Silent Accumulation Phase — ${symbol}**

Harga relatif tenang. Volume tidak meledak, tapi likuiditas stabil dan holders terus bertambah diam-diam. Ini fase di mana smart money biasanya membangun posisi sebelum sinyal besar muncul.

Jaringan sedang mengisi energi. Belum ada ledakan, tapi fondasinya semakin kuat.

Sabar adalah bagian dari strategi.""",

        "correction": f"""🔻 **Network Recalibration — ${symbol}**

Sinyal melemah sementara. Beberapa node melepaskan posisi. Ini normal dalam siklus — jaringan sedang membersihkan noise sebelum siklus berikutnya.

Pantau apakah holders tetap bertahan atau ikut kabur. Kalau foundation masih utuh, koreksi ini bisa jadi entry yang lebih baik.""",

        "observation": f"""👁️ **Monitoring Protocol — ${symbol}**

Belum ada sinyal ekstrem. Jaringan masih dalam mode observasi. Data menunjukkan pergerakan normal tanpa anomali besar.

Tetap waspada. Runner sejati muncul dari fase yang paling membosankan sekalipun."""
    }

    return lores.get(theme, lores["observation"])

def analyze_and_recommend(pair, holders=None):
    if not pair:
        return "HOLD", "Data tidak tersedia."

    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)

    reasons = []
    score = 0

    if liquidity < 15000:
        reasons.append("⚠️ Liquidity rendah (risiko tinggi)")
        score -= 2
    elif liquidity > 50000:
        reasons.append("✅ Liquidity cukup sehat")
        score += 1

    if volume_1h > 30000 and price_change_1h > 8:
        reasons.append("🔥 Volume + price action kuat (momentum)")
        score += 2
    elif volume_1h > 10000:
        reasons.append("📊 Volume sedang aktif")
        score += 1

    if holders:
        if holders > 800:
            reasons.append(f"👥 Holders sudah {holders}")
            score += 1
        elif holders < 200:
            reasons.append(f"👥 Holders masih rendah ({holders})")
            score -= 1

    if price_change_1h > 25:
        reasons.append("⚡ Pergerakan sangat agresif (hati-hati FOMO)")
        score -= 1

    if score >= 3:
        decision = "BUY"
        alasan = "Sinyal momentum + struktur cukup baik untuk spekulasi terukur."
    elif score <= -1:
        decision = "SELL / AVOID"
        alasan = "Risiko lebih tinggi dibanding potensi saat ini."
    else:
        decision = "HOLD / OBSERVE"
        alasan = "Belum ada edge yang jelas. Tunggu konfirmasi lebih kuat."

    return decision, " | ".join(reasons) + f"\n\n**Kesimpulan:** {alasan}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌌 **Solana Lore Runner Bot** aktif.\n\n"
        "Command:\n"
        "/add <CA> — tambah token ke watchlist\n"
        "/remove <CA> — hapus dari watchlist\n"
        "/list — lihat watchlist\n"
        "/check <CA> — analisis langsung + lore + rekomendasi\n\n"
        "Bot akan kirim alert otomatis jika ada pergerakan signifikan."
    )

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Contoh: /add 7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        return
    ca = context.args[0].strip()
    wl = load_watchlist()
    wl[ca] = {"added": datetime.now().isoformat()}
    save_watchlist(wl)
    await update.message.reply_text(f"✅ Token `{ca}` ditambahkan ke watchlist.")

async def remove_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Contoh: /remove <CA>")
        return
    ca = context.args[0].strip()
    wl = load_watchlist()
    if ca in wl:
        del wl[ca]
        save_watchlist(wl)
        await update.message.reply_text(f"🗑️ Token `{ca}` dihapus.")
    else:
        await update.message.reply_text("Token tidak ada di watchlist.")

async def list_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wl = load_watchlist()
    if not wl:
        await update.message.reply_text("Watchlist kosong.")
        return
    text = "📋 **Watchlist:**\n" + "\n".join([f"`{ca}`" for ca in wl.keys()])
    await update.message.reply_text(text)

async def check_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Contoh: /check <Contract_Address>")
        return

    ca = context.args[0].strip()
    await update.message.reply_text("📡 Scanning network...")

    pair = get_dexscreener_data(ca)
    if not pair:
        await update.message.reply_text("❌ Data tidak ditemukan. Pastikan CA benar.")
        return

    symbol = pair.get("baseToken", {}).get("symbol", "UNKNOWN")
    name = pair.get("baseToken", {}).get("name", "Unknown")
    price = pair.get("priceUsd", "0")
    price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mcap = float(pair.get("marketCap", 0) or 0)

    holders = get_holder_count(ca)

    lore = generate_organic_tech_lore(symbol, name, price_change_1h, volume_1h, liquidity, holders, mcap)
    decision, alasan = analyze_and_recommend(pair, holders)

    holder_text = f"• Holders: **{holders}**\n" if holders else "• Holders: (aktifkan Birdeye API key untuk data ini)\n"

    message = f"""
{lore}

━━━━━━━━━━━━━━━━
📊 **Data Real-time**
• Symbol: **${symbol}**
• Price: `${price}`
• 1h Change: `{price_change_1h:+.2f}%`
• Volume 1h: `${volume_1h:,.0f}`
• Liquidity: `${liquidity:,.0f}`
• Market Cap: `${mcap:,.0f}`
{holder_text}
• Pair: {pair.get('dexId', 'unknown').upper()}

🎯 **Rekomendasi: {decision}**
{alasan}

_Bukan nasihat keuangan. DYOR. Risiko tinggi._
"""
    await update.message.reply_text(message, parse_mode="Markdown")

async def periodic_check(context: ContextTypes.DEFAULT_TYPE):
    wl = load_watchlist()
    if not wl or not CHAT_ID:
        return

    for ca in list(wl.keys()):
        pair = get_dexscreener_data(ca)
        if not pair:
            continue

        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
        volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)

        if abs(price_change_1h) > 12 or volume_1h > 80000:
            symbol = pair.get("baseToken", {}).get("symbol", "TOKEN")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"🚨 **Alert ${symbol}**\n1h: `{price_change_1h:+.2f}%` | Vol 1h: `${volume_1h:,.0f}`\nGunakan /check {ca} untuk analisis lengkap + lore."
            )
        time.sleep(1)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_token))
    app.add_handler(CommandHandler("remove", remove_token))
    app.add_handler(CommandHandler("list", list_tokens))
    app.add_handler(CommandHandler("check", check_token))

    job_queue = app.job_queue
    job_queue.run_repeating(periodic_check, interval=300, first=10)

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()

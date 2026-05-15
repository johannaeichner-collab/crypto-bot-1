import os
import aiohttp
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

COINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "ripple": "XRP",
    "cardano": "ADA",
    "litecoin": "LTC",
    "avalanche-2": "AVAX",
    "hedera-hashgraph": "HBAR",
    "crypto-com-chain": "CRO",
    "matic-network": "POL",
    "render-token": "RENDER",
    "vechain": "VET",
    "fetch-ai": "FET",
    "decentraland": "MANA"
}

tranches = []

async def get_prices():
    ids = ",".join(COINS.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd,eur&include_24hr_change=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

def format_price(n):
    if n >= 1000:
        return f"${n:,.0f}"
    elif n >= 1:
        return f"${n:.2f}"
    else:
        return f"${n:.5f}"

def format_prices_text(data):
    lines = []
    for coin_id, sym in COINS.items():
        d = data.get(coin_id, {})
        price = d.get("usd", 0)
        chg = d.get("usd_24h_change", 0)
        arrow = "↑" if chg >= 0 else "↓"
        lines.append(f"{sym}: {format_price(price)} {arrow}{abs(chg):.1f}%")
    return "\n".join(lines)

def ask_ai(system, user_message):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 800
        },
        timeout=30
    )
    return response.json()["choices"][0]["message"]["content"]

async def generate_briefing(briefing_type, prices_text):
    tranche_info = ""
    if tranches:
        tranche_info = "\n\nAktive Tranchen:\n" + "\n".join(
            [f"- {t['coin']}: Ziel ${t['target']}, Betrag €{t['amount']}" for t in tranches]
        )
    prompt = f"""Aktuelle Kurse:
{prices_text}
{tranche_info}

Erstelle ein kompaktes {briefing_type} auf Deutsch. Max 150 Wörter. Direkt und klar. Was fällt heute auf?"""
    system = "Du bist ein Crypto-Assistent. Antworte auf Deutsch, kurz und direkt."
    return ask_ai(system, prompt)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hallo Johanna! Ich bin dein Crypto-Assistent.\n\n"
        "Befehle:\n"
        "/preise – Aktuelle Kurse\n"
        "/mittag – Mittags-Briefing\n"
        "/abend – Abend-Briefing\n"
        "/tranche BTC 75000 500 – Tranche anlegen\n"
        "/tranchen – Alle Tranchen\n\n"
        "Oder stell mir einfach eine Frage!"
    )

async def preise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Lade Preise...")
    try:
        data = await get_prices()
        text = "📊 *Aktuelle Kurse*\n\n" + format_prices_text(data)
        now = datetime.utcnow()
        text += f"\n\n_Stand: {now.strftime('%H:%M')} UTC_"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def mittag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Briefing...")
    try:
        data = await get_prices()
        briefing = await generate_briefing("Mittags-Briefing", format_prices_text(data))
        await update.message.reply_text(briefing)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def abend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Briefing...")
    try:
        data = await get_prices()
        briefing = await generate_briefing("Abend-Briefing", format_prices_text(data))
        await update.message.reply_text(briefing)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def tranche_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Format: /tranche BTC 75000 500\n(Coin, Zielpreis USD, Betrag EUR)")
        return
    coin, target, amount = args[0].upper(), args[1], args[2]
    tranches.append({"coin": coin, "target": target, "amount": amount})
    await update.message.reply_text(f"✅ Tranche gespeichert:\n{coin} bei ${target} für €{amount}")

async def tranchen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tranches:
        await update.message.reply_text("Noch keine Tranchen. Mit /tranche BTC 75000 500 anlegen.")
        return
    try:
        data = await get_prices()
        lines = ["📋 *Deine Tranchen*\n"]
        for t in tranches:
            coin_id = next((k for k, v in COINS.items() if v == t['coin']), None)
            current = data.get(coin_id, {}).get("usd", 0) if coin_id else 0
            target = float(t['target'])
            diff = ((current - target) / target * 100) if target else 0
            status = "✅ Kaufzone!" if current <= target * 1.02 else f"{diff:+.1f}% vom Ziel"
            lines.append(f"*{t['coin']}*: Ziel ${t['target']} | €{t['amount']}\nAktuell: {format_price(current)} | {status}\n")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("Denke nach...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        system = f"""Du bist Johannas persönlicher Crypto-Assistent. Sie ist Bauzeichnerin und investiert nebenberuflich in Krypto. Ihre Coins: BTC, ETH, XRP, ADA, LTC, AVAX, HBAR, CRO, POL, RENDER, VET, FET, MANA.

Aktuelle Preise:
{prices_text}

Antworte auf Deutsch. Kurz, direkt, klar."""
        reply = ask_ai(system, text)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def auto_briefing(context: ContextTypes.DEFAULT_TYPE):
    hour = datetime.utcnow().hour
    briefing_type = "Mittags-Briefing" if hour == 10 else "Abend-Briefing"
    try:
        data = await get_prices()
        briefing = await generate_briefing(briefing_type, format_prices_text(data))
        await context.bot.send_message(chat_id=CHAT_ID, text=briefing)
    except Exception as e:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Fehler: {e}")

async def check_tranches(context: ContextTypes.DEFAULT_TYPE):
    if not tranches:
        return
    try:
        data = await get_prices()
        alerts = []
        for t in tranches:
            coin_id = next((k for k, v in COINS.items() if v == t['coin']), None)
            if not coin_id:
                continue
            current = data.get(coin_id, {}).get("usd", 0)
            target = float(t['target'])
            if current <= target * 1.02:
                alerts.append(f"🚨 *{t['coin']}* bei Kaufzone!\nZiel: ${t['target']} | Aktuell: {format_price(current)}\nBetrag: €{t['amount']}")
        if alerts:
            await context.bot.send_message(chat_id=CHAT_ID, text="\n\n".join(alerts), parse_mode="Markdown")
    except:
        pass

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("preise", preise))
    app.add_handler(CommandHandler("mittag", mittag_cmd))
    app.add_handler(CommandHandler("abend", abend_cmd))
    app.add_handler(CommandHandler("tranche", tranche_cmd))
    app.add_handler(CommandHandler("tranchen", tranchen_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    job_queue = app.job_queue
    job_queue.run_daily(auto_briefing, time=datetime.strptime("10:00", "%H:%M").time())
    job_queue.run_daily(auto_briefing, time=datetime.strptime("18:00", "%H:%M").time())
    job_queue.run_repeating(check_tranches, interval=1800, first=60)

    print("Bot läuft...")
    app.run_polling()

if __name__ == "__main__":
    main()

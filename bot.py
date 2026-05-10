import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic
import json

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

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

# Tranchen speichern (in-memory, kann später in Datei/DB gespeichert werden)
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

async def generate_briefing(briefing_type: str, prices_text: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    tranche_info = ""
    if tranches:
        tranche_info = "\n\nAktive Tranchen:\n" + "\n".join(
            [f"- {t['coin']}: Ziel ${t['target']}, Betrag €{t['amount']}" for t in tranches]
        )
    
    prompt = f"""Du bist Johannas Crypto-Assistent. Erstelle ein kompaktes {briefing_type} auf Deutsch.

Aktuelle Kurse:
{prices_text}
{tranche_info}

Format:
📊 *{briefing_type}* – {datetime.now().strftime('%d.%m.%Y %H:%M')}

Kurzer Marktüberblick (2-3 Sätze)
Was fällt heute auf?
{('Tranche-Check: Welche Zielpreise sind nah?' if tranches else '')}

Max 150 Wörter. Direkt und klar."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

async def ask_claude(question: str, prices_text: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    tranche_info = ""
    if tranches:
        tranche_info = "\n\nAktive Tranchen von Johanna:\n" + "\n".join(
            [f"- {t['coin']}: Ziel ${t['target']}, Betrag €{t['amount']}" for t in tranches]
        )
    
    system = f"""Du bist Johannas persönlicher Crypto-Assistent. Sie ist Bauzeichnerin und investiert nebenberuflich in Krypto. Ihre Coins: BTC, ETH, XRP, ADA, LTC, AVAX, HBAR, CRO, POL, RENDER, VET, FET, MANA.

Aktuelle Preise:
{prices_text}
{tranche_info}

Antworte auf Deutsch. Kurz, direkt, klar. Keine Finanzberatung, aber Zusammenhänge erklären und Strategien strukturieren ist okay. Für Telegram: nutze *fett* und einfache Formatierung."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": question}]
    )
    return message.content[0].text

# === Telegram Commands ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hallo Johanna! Ich bin dein Crypto-Assistent.\n\n"
        "Befehle:\n"
        "/preise – Aktuelle Kurse\n"
        "/mittag – Mittags-Briefing\n"
        "/abend – Abend-Briefing\n"
        "/tranche BTC 75000 500 – Tranche anlegen (Coin, Zielpreis, Betrag €)\n"
        "/tranchen – Alle Tranchen anzeigen\n"
        "/hilfe – Alle Befehle\n\n"
        "Oder stell mir einfach eine Frage!"
    )

async def preise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Lade Preise...")
    try:
        data = await get_prices()
        text = "📊 *Aktuelle Kurse*\n\n" + format_prices_text(data)
        text += f"\n\n_Stand: {datetime.now().strftime('%H:%M Uhr')}_"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def mittag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Mittags-Briefing...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        briefing = await generate_briefing("Mittags-Briefing", prices_text)
        await update.message.reply_text(briefing, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def abend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Abend-Briefing...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        briefing = await generate_briefing("Abend-Briefing", prices_text)
        await update.message.reply_text(briefing, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def tranche_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Format: /tranche BTC 75000 500\n(Coin, Zielpreis in USD, Betrag in EUR)")
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
            coin_id = next((k for k,v in COINS.items() if v == t['coin']), None)
            current = data.get(coin_id, {}).get("usd", 0) if coin_id else 0
            target = float(t['target'])
            diff = ((current - target) / target * 100) if target else 0
            status = "✅ Kaufzone!" if current <= target * 1.02 else f"{diff:+.1f}% vom Ziel"
            lines.append(f"*{t['coin']}*: Ziel ${t['target']} | €{t['amount']}\nAktuell: {format_price(current)} | {status}\n")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def hilfe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Befehle*\n\n"
        "/preise – Live-Kurse aller Coins\n"
        "/mittag – Mittags-Briefing\n"
        "/abend – Abend-Briefing\n"
        "/tranche BTC 75000 500 – Tranche anlegen\n"
        "/tranchen – Tranchen + Status\n\n"
        "Oder schreib mir einfach auf Deutsch – ich beantworte alle Fragen zu Markt und Strategie!",
        parse_mode="Markdown"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("Denke nach...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        reply = await ask_claude(text, prices_text)
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

# === Automatische Briefings ===

async def auto_briefing(context: ContextTypes.DEFAULT_TYPE):
    hour = datetime.now().hour
    briefing_type = "Mittags-Briefing" if hour == 12 else "Abend-Briefing"
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        briefing = await generate_briefing(briefing_type, prices_text)
        await context.bot.send_message(chat_id=CHAT_ID, text=briefing, parse_mode="Markdown")
    except Exception as e:
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Fehler beim Auto-Briefing: {e}")

async def check_tranches(context: ContextTypes.DEFAULT_TYPE):
    if not tranches:
        return
    try:
        data = await get_prices()
        alerts = []
        for t in tranches:
            coin_id = next((k for k,v in COINS.items() if v == t['coin']), None)
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
    app.add_handler(CommandHandler("hilfe", hilfe))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Automatische Briefings: 12:00 und 20:00
    job_queue = app.job_queue
    job_queue.run_daily(auto_briefing, time=datetime.strptime("12:00", "%H:%M").time())
    job_queue.run_daily(auto_briefing, time=datetime.strptime("20:00", "%H:%M").time())
    # Tranche-Check alle 30 Minuten
    job_queue.run_repeating(check_tranches, interval=1800, first=60)

    print("Bot läuft...")
    app.run_polling()

if __name__ == "__main__":
    main()

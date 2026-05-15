import os
import aiohttp
import requests
import base64
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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
    "decentraland": "MANA",
    "chainlink": "LINK"
}

def supabase_get(table, params=""):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}{params}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    )
    return r.json()

def supabase_post(table, data):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
        json=data
    )

def supabase_delete(table, params):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}{params}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    )

def get_tranchen():
    result = supabase_get("Tranchen", "?status=eq.aktiv")
    if isinstance(result, list):
        return result
    return []

def save_tranche(coin, zielpreis, betrag):
    supabase_post("Tranchen", {"coin": coin, "zielpreis": zielpreis, "betrag": betrag, "status": "aktiv"})

def mark_tranche_erreicht(tranche_id):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/Tranchen?id=eq.{tranche_id}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
        json={"status": "erreicht"}
    )

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
        arrow = "up" if chg >= 0 else "down"
        lines.append(f"{sym}: {format_price(price)} {arrow}{abs(chg):.1f}%")
    return "\n".join(lines)

def ask_ai(system, user_message):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_message}],
            "max_tokens": 1000
        },
        timeout=30
    )
    return response.json()["choices"][0]["message"]["content"]

def ask_ai_with_image(system, user_message, image_base64, mime_type="image/jpeg"):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": user_message},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}}
                ]}
            ],
            "max_tokens": 1000
        },
        timeout=60
    )
    return response.json()["choices"][0]["message"]["content"]

def save_analyse(coin, inhalt):
    datum = datetime.now().strftime("%d.%m.%Y")
    supabase_post("Analysen", {"Coin": coin, "Inhalt": inhalt, "Datum": datum})

def get_analysen():
    result = supabase_get("Analysen", "?order=id.desc&limit=20")
    if isinstance(result, list):
        return result
    return []

def format_analysen():
    analysen = get_analysen()
    if not analysen:
        return ""
    lines = []
    for a in analysen[:10]:
        lines.append(f"[{a.get('Datum','')}] {a.get('Coin','')}: {a.get('Inhalt','')[:200]}")
    return "\n\n".join(lines)

async def generate_briefing(briefing_type, prices_text):
    tranchen = get_tranchen()
    tranche_info = ""
    if tranchen:
        tranche_info = "\n\nAktive Tranchen:\n" + "\n".join(
            [f"- {t['coin']}: Ziel ${t['zielpreis']}, Betrag EUR{t['betrag']}" for t in tranchen]
        )

    analysen_text = format_analysen()
    analysen_info = f"\n\nGespeicherte HKCM-Analysen:\n{analysen_text}" if analysen_text else ""
    heute = datetime.now().strftime("%d.%m.%Y")

    prompt = f"""Heute ist der {heute}. Aktuelle Kurse:
{prices_text}
{tranche_info}
{analysen_info}

Erstelle ein kompaktes {briefing_type} auf Deutsch. Max 200 Woerter.
Beziehe dich auf die HKCM-Analysen wenn vorhanden.
Erinnere Johanna wenn laut Analyse ein Einstieg oder Ausstieg relevant sein koennte.
Direkt und klar. Was ist heute wichtig?"""

    system = "Du bist Johannas persoenlicher Crypto-Assistent. Antworte auf Deutsch, kurz und direkt."
    return ask_ai(system, prompt)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hallo Johanna! Ich bin dein Crypto-Assistent.\n\n"
        "Befehle:\n"
        "/preise - Aktuelle Kurse\n"
        "/mittag - Mittags-Briefing\n"
        "/abend - Abend-Briefing\n"
        "/tranche BTC 75000 500 - Tranche anlegen\n"
        "/tranchen - Alle Tranchen\n"
        "/analysen - Gespeicherte HKCM-Analysen\n\n"
        "Schick mir einen HKCM-Screenshot und ich speichere die Analyse!\n"
        "Oder stell mir eine Frage!"
    )

async def preise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Lade Preise...")
    try:
        data = await get_prices()
        text = "Aktuelle Kurse\n\n" + format_prices_text(data)
        now = datetime.utcnow()
        text += f"\n\nStand: {now.strftime('%H:%M')} UTC"
        await update.message.reply_text(text)
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
    coin, zielpreis, betrag = args[0].upper(), args[1], args[2]
    save_tranche(coin, zielpreis, betrag)
    await update.message.reply_text(f"Tranche gespeichert:\n{coin} bei ${zielpreis} fuer EUR{betrag}")

async def tranchen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tranchen = get_tranchen()
        if not tranchen:
            await update.message.reply_text("Noch keine Tranchen. Mit /tranche BTC 75000 500 anlegen.")
            return
        data = await get_prices()
        lines = ["Deine aktiven Tranchen\n"]
        for t in tranchen:
            coin_id = next((k for k, v in COINS.items() if v == t['coin']), None)
            current = data.get(coin_id, {}).get("usd", 0) if coin_id else 0
            target = float(t['zielpreis'])
            diff = ((current - target) / target * 100) if target else 0
            status = "Kaufzone!" if current <= target * 1.02 else f"{diff:+.1f}% vom Ziel"
            lines.append(f"{t['coin']}: Ziel ${t['zielpreis']} | EUR{t['betrag']}\nAktuell: {format_price(current)} | {status}\n")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def analysen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        analysen = get_analysen()
        if not analysen:
            await update.message.reply_text("Noch keine Analysen gespeichert.")
            return
        lines = ["Gespeicherte HKCM-Analysen:\n"]
        for a in analysen[:5]:
            lines.append(f"{a.get('Datum','')} - {a.get('Coin','')}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Analysiere HKCM-Screenshot...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(img_bytes).decode("utf-8")

        data = await get_prices()
        prices_text = format_prices_text(data)

        user_prompt = f"""Das ist ein Screenshot einer HKCM Krypto-Analyse.
Extrahiere folgende Infos strukturiert:
- Coin (Name und Symbol)
- Datum der Analyse
- Primaerszenario
- Alternativszenario
- Unterstuetzungen (Preise)
- Widerstaende (Preise)
- Handelsmoeglichkeiten (konkrete Einstiegszonen falls vorhanden)

Dann: kurze Einschaetzung basierend auf aktuellem Kurs.

Aktuelle Kurse:
{prices_text}"""

        system = "Du bist Johannas Crypto-Assistent. Analysiere HKCM-Screenshots strukturiert auf Deutsch."
        reply = ask_ai_with_image(system, user_prompt, image_base64)

        coin_extract_prompt = f"Welcher Coin-Symbol (z.B. BTC, ETH, RENDER) wird in diesem Text analysiert? Antworte nur mit dem Symbol: {reply[:200]}"
        coin_symbol = ask_ai("Antworte nur mit dem Coin-Symbol.", coin_extract_prompt).strip().upper()

        save_analyse(coin_symbol, reply)

        await update.message.reply_text(reply)
        await update.message.reply_text(f"Analyse fuer {coin_symbol} gespeichert!")

    except Exception as e:
        await update.message.reply_text(f"Fehler beim Bildlesen: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("Denke nach...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        analysen_text = format_analysen()
        tranchen = get_tranchen()
        tranche_text = "\n".join([f"- {t['coin']}: Ziel ${t['zielpreis']}" for t in tranchen]) if tranchen else ""

        system = f"""Du bist Johannas persoenlicher Crypto-Assistent. Sie ist Bauzeichnerin und investiert nebenberuflich in Krypto.
Ihre Coins: BTC, ETH, XRP, ADA, LTC, AVAX, HBAR, CRO, POL, RENDER, VET, FET, MANA, LINK.

Aktuelle Preise:
{prices_text}

{f'Aktive Tranchen:{chr(10)}{tranche_text}' if tranche_text else ''}

{f'Gespeicherte HKCM-Analysen:{chr(10)}{analysen_text}' if analysen_text else ''}

Antworte auf Deutsch. Kurz, direkt, klar. Beziehe dich auf HKCM-Analysen wenn relevant."""

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
    try:
        tranchen = get_tranchen()
        if not tranchen:
            return
        data = await get_prices()
        for t in tranchen:
            coin_id = next((k for k, v in COINS.items() if v == t['coin']), None)
            if not coin_id:
                continue
            current = data.get(coin_id, {}).get("usd", 0)
            target = float(t['zielpreis'])
            if current <= target * 1.02:
                await context.bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"ALARM: {t['coin']} bei Kaufzone!\nZiel: ${t['zielpreis']} | Aktuell: {format_price(current)}\nBetrag: EUR{t['betrag']}"
                )
                mark_tranche_erreicht(t['id'])
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
    app.add_handler(CommandHandler("analysen", analysen_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, image_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    job_queue = app.job_queue
    job_queue.run_daily(auto_briefing, time=datetime.strptime("10:00", "%H:%M").time())
    job_queue.run_daily(auto_briefing, time=datetime.strptime("18:00", "%H:%M").time())
    job_queue.run_repeating(check_tranches, interval=1800, first=60)

    print("Bot laeuft...")
    app.run_polling()

if __name__ == "__main__":
    main()

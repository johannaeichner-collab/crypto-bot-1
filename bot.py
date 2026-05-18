import os
import aiohttp
import requests
import base64
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY")

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
            "max_tokens": 1200
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

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = r.json()
        value = int(data["data"][0]["value"])
        label = data["data"][0]["value_classification"]
        return value, label
    except:
        return None, None

def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json()
        dominance = data["data"]["market_cap_percentage"]["btc"]
        return round(dominance, 1)
    except:
        return None

def get_oil_price():
    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/quote?symbol=USOIL&token={FINNHUB_KEY}",
            timeout=10
        )
        data = r.json()
        price = data.get("c")
        change = data.get("dp")
        if price:
            return round(price, 2), round(change, 2) if change else None
        return None, None
    except:
        return None, None

def get_economic_calendar():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        r = requests.get(
            f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={day_after}&token={FINNHUB_KEY}",
            timeout=10
        )
        data = r.json()
        events = data.get("economicCalendar", [])

        important = []
        keywords = ["fed", "fomc", "interest rate", "cpi", "inflation", "unemployment", "nonfarm", "gdp", "ppi", "ecb"]

        for e in events:
            name = e.get("event", "").lower()
            impact = e.get("impact", "").lower()
            if any(kw in name for kw in keywords) and impact in ["high", "medium"]:
                important.append({
                    "date": e.get("time", ""),
                    "event": e.get("event", ""),
                    "actual": e.get("actual"),
                    "forecast": e.get("forecast"),
                    "previous": e.get("previous"),
                    "impact": impact
                })
        return important[:5]
    except:
        return []

def get_crypto_news(since_hour=None):
    feeds = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("Reuters", "https://feeds.reuters.com/reuters/technologyNews"),
        ("Decrypt", "https://decrypt.co/feed"),
    ]
    articles = []
    keywords = ["bitcoin", "crypto", "btc", "ethereum", "blockchain", "sec", "etf",
                "fed", "regulation", "reserve", "krypto", "eu", "clarity", "congress",
                "iran", "geopolit", "oil", "oel", "trump", "powell"]

    for source, url in feeds:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:5]
            for item in items:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "").strip()[:300]
                if title and link and any(kw in title.lower() or kw in desc.lower() for kw in keywords):
                    articles.append({
                        "title": title,
                        "link": link,
                        "desc": desc,
                        "source": source
                    })
                    if len(articles) >= 6:
                        break
        except:
            continue
        if len(articles) >= 6:
            break
    return articles[:3]

def summarize_article(title, desc, link):
    prompt = f"""Fasse diesen Artikel in 3-5 Saetzen auf Deutsch zusammen. Erklaere was passiert ist und was das fuer Crypto bedeutet.

Titel: {title}
Inhalt: {desc}

Format:
[3-5 Saetze Zusammenfassung]
Bedeutung fuer Crypto: [1 Satz]"""
    return ask_ai("Du bist ein Finanzjournalist. Fasse Artikel kurz und verstaendlich zusammen.", prompt)

async def generate_briefing_msg1(briefing_type, prices_data, prices_text):
    btc = prices_data.get("bitcoin", {})
    eth = prices_data.get("ethereum", {})
    fg_value, fg_label = get_fear_greed()
    btc_dom = get_btc_dominance()
    oil_price, oil_change = get_oil_price()
    heute = datetime.now().strftime("%d.%m.%Y %H:%M")

    btc_chg = btc.get("usd_24h_change", 0)
    eth_chg = eth.get("usd_24h_change", 0)

    altcoin_lines = []
    for coin_id, sym in COINS.items():
        if sym in ["BTC", "ETH"]:
            continue
        d = prices_data.get(coin_id, {})
        chg = d.get("usd_24h_change", 0)
        price = d.get("usd", 0)
        diff = chg - btc_chg
        if diff > 1:
            status = "staerker als BTC"
        elif diff < -1:
            status = "schwaecher als BTC"
        else:
            status = "aehnlich wie BTC"
        altcoin_lines.append(f"{sym}: {format_price(price)} ({chg:+.1f}%) - {status}")

    prompt = f"""Erstelle Nachricht 1 des {briefing_type} fuer Johanna. Heute: {heute}

BITCOIN: ${format_price(btc.get('usd',0))} ({btc_chg:+.1f}%)
ETHEREUM: ${format_price(eth.get('usd',0))} ({eth_chg:+.1f}%)

ALTCOINS:
{chr(10).join(altcoin_lines)}

MAKRO:
Fear & Greed: {fg_value}/100 ({fg_label}) - {"Angst" if fg_value and fg_value < 40 else "Gier" if fg_value and fg_value > 60 else "Neutral"}
BTC Dominanz: {btc_dom}%
Oelpreis: ${oil_price} ({oil_change:+.1f}%) - {"steigend" if oil_change and oil_change > 0 else "fallend"}

Formatiere so:

MARKT {briefing_type.upper()} - {heute}

BTC Bitcoin
[2-3 Saetze: Kursbewegung erklaeren, wichtige Level, HKCM-Bezug falls relevant]

ETH Ethereum  
[2 Saetze: Kursbewegung, Verhaeltnis zu BTC]

ALTCOIN-LAGE
BTC Dominanz {btc_dom}% - [erklaere was das bedeutet, Bitcoin Season oder Altcoin Season]
[Liste alle Altcoins mit Status, gruppiere: staerker / aehnlich / schwaecher als BTC]

MARKTSTIMMUNG
Fear & Greed: {fg_value}/100 - [erklaere was das historisch bedeutet]
Oelpreis: ${oil_price} - [erklaere Zusammenhang mit Crypto-Markt]

Max 350 Woerter. Auf Deutsch."""

    system = "Du bist Johannas Crypto-Assistent. Erklaere alles verstaendlich auf Deutsch."
    return ask_ai(system, prompt)

async def generate_briefing_msg2(briefing_type, prices_data):
    analysen_text = format_analysen()
    tranchen = get_tranchen()
    calendar = get_economic_calendar()
    news = get_crypto_news()
    heute = datetime.now().strftime("%d.%m.%Y")

    news_summaries = []
    for n in news:
        summary = summarize_article(n['title'], n['desc'], n['link'])
        news_summaries.append(f"{n['title']}\n{summary}\nQuelle: {n['source']}\n{n['link']}")

    calendar_text = ""
    if calendar:
        calendar_lines = []
        for e in calendar:
            actual = f" | Aktuell: {e['actual']}" if e['actual'] else " | Ergebnis ausstehend"
            forecast = f" | Prognose: {e['forecast']}" if e['forecast'] else ""
            calendar_lines.append(f"{e['date'][:10]} - {e['event']}{actual}{forecast}")
        calendar_text = "\n".join(calendar_lines)

    tranche_text = ""
    if tranchen:
        tranche_text = "\n".join([f"- {t['coin']}: Ziel ${t['zielpreis']}" for t in tranchen])

    prompt = f"""Erstelle Nachricht 2 des {briefing_type} fuer Johanna. Heute: {heute}

NEWS:
{chr(10).join(news_summaries)}

WIRTSCHAFTSKALENDER (naechste 2 Tage):
{calendar_text if calendar_text else "Keine wichtigen Termine"}

HKCM-ANALYSEN:
{analysen_text[:1000] if analysen_text else "Keine gespeichert"}

AKTIVE TRANCHEN:
{tranche_text if tranche_text else "Keine"}

Formatiere so:

TOP NEWS

1. [Titel]
[Zusammenfassung 3-4 Saetze]
Bedeutung: [1 Satz was das fuer Crypto bedeutet]
Quelle: [Name] | [Link]

2. [gleich]

3. [gleich]

WIRTSCHAFTSKALENDER
[Wenn wichtige Termine morgen/uebermorgen: Vorwarnung mit Erklaerung was der Termin bedeutet]
[Wenn heute Ergebnis vorliegt: Was war das Ergebnis und was bedeutet es]

HKCM-CHECK
[Welche deiner Coins naehern sich laut gespeicherten Analysen einer Kauf- oder Verkaufszone?]

HANDLUNGSHINWEISE
[2-3 konkrete Punkte was heute relevant sein koennte]

Max 400 Woerter. Auf Deutsch."""

    system = "Du bist Johannas Crypto-Assistent. Informiere detailliert aber verstaendlich auf Deutsch."
    return ask_ai(system, prompt)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hallo Johanna! Ich bin dein Crypto-Assistent.\n\n"
        "Befehle:\n"
        "/preise - Aktuelle Kurse\n"
        "/mittag - Mittags-Briefing\n"
        "/abend - Abend-Briefing\n"
        "/makro - Makro-Update mit News\n"
        "/tranche BTC 75000 500 - Tranche anlegen\n"
        "/tranchen - Alle Tranchen\n"
        "/analysen - HKCM-Analysen\n\n"
        "Schick mir einen HKCM-Screenshot oder Text mit 'HKCM'!\n"
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

async def makro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Lade Makro-Daten und News...")
    try:
        fg_value, fg_label = get_fear_greed()
        btc_dom = get_btc_dominance()
        oil_price, oil_change = get_oil_price()
        news = get_crypto_news()
        calendar = get_economic_calendar()

        lines = [f"MAKRO-UPDATE {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"]

        if fg_value is not None:
            if fg_value <= 25:
                fg_erkl = "Extreme Angst - historisch oft Kaufgelegenheit"
            elif fg_value <= 45:
                fg_erkl = "Angst - Markt ist vorsichtig"
            elif fg_value <= 55:
                fg_erkl = "Neutral - keine klare Richtung"
            elif fg_value <= 75:
                fg_erkl = "Gier - Markt laeuft gut, Vorsicht bei Einstiegen"
            else:
                fg_erkl = "Extreme Gier - Markt ueberhitzt, Ruecksetzer moeglich"
            lines.append(f"Fear & Greed: {fg_value}/100 ({fg_label})\n-> {fg_erkl}\n")

        if btc_dom is not None:
            if btc_dom > 55:
                dom_erkl = "Bitcoin Season - Altcoins verlieren, Kapital fliesst in BTC"
            elif btc_dom > 45:
                dom_erkl = "Ausgeglichen - kein klarer Trend"
            else:
                dom_erkl = "Altcoin Season moeglich - Kapital rotiert von BTC in Altcoins"
            lines.append(f"BTC Dominanz: {btc_dom}%\n-> {dom_erkl}\n")

        if oil_price:
            oil_erkl = "Hoher Oelpreis signalisiert geopolitische Spannung - oft negativ fuer Risk-Assets" if oil_price > 85 else "Oelpreis stabil - kein Stresssignal"
            lines.append(f"Oelpreis: ${oil_price} ({oil_change:+.1f}%)\n-> {oil_erkl}\n")

        if calendar:
            lines.append("Wirtschaftskalender:")
            for e in calendar[:3]:
                lines.append(f"- {e['date'][:10]}: {e['event']}")

        if news:
            lines.append("\nAktuelle News:")
            for n in news:
                summary = summarize_article(n['title'], n['desc'], n['link'])
                lines.append(f"\n{n['title']}\n{summary}\nQuelle: {n['source']}\n{n['link']}")

        await update.message.reply_text("\n".join(lines), disable_web_page_preview=False)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def mittag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Briefing - einen Moment...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        msg1 = await generate_briefing_msg1("Mittags-Briefing", data, prices_text)
        msg2 = await generate_briefing_msg2("Mittags-Briefing", data)
        await update.message.reply_text(msg1, disable_web_page_preview=True)
        await update.message.reply_text(msg2, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def abend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Erstelle Briefing - einen Moment...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        msg1 = await generate_briefing_msg1("Abend-Briefing", data, prices_text)
        msg2 = await generate_briefing_msg2("Abend-Briefing", data)
        await update.message.reply_text(msg1, disable_web_page_preview=True)
        await update.message.reply_text(msg2, disable_web_page_preview=True)
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
        if not analysen or not isinstance(analysen, list):
            await update.message.reply_text("Noch keine Analysen gespeichert.")
            return
        latest = {}
        for a in analysen:
            coin = a.get('Coin', '')
            if coin not in latest:
                latest[coin] = a.get('Datum', '')
        lines = ["Letzte HKCM-Analysen pro Coin:\n"]
        for coin in sorted(latest.keys()):
            lines.append(f"{latest[coin]} - {coin}")
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
        coin_extract_prompt = f"Welcher Coin-Symbol wird in diesem Text analysiert? Antworte nur mit dem Symbol: {reply[:200]}"
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

        if "HKCM" in text.upper():
            coin_extract_prompt = f"Welcher Coin-Symbol wird in diesem Text analysiert? Antworte nur mit dem Symbol: {text[:300]}"
            coin_symbol = ask_ai("Antworte nur mit dem Coin-Symbol.", coin_extract_prompt).strip().upper()
            save_analyse(coin_symbol, text)
            await update.message.reply_text(f"Analyse fuer {coin_symbol} gespeichert!")
            return

        system = f"""Du bist Johannas persoenlicher Crypto-Assistent. Sie ist Bauzeichnerin und investiert nebenberuflich in Krypto.
Ihre Coins: BTC, ETH, XRP, ADA, LTC, AVAX, HBAR, CRO, POL, RENDER, VET, FET, MANA, LINK.
Aktuelle Preise:
{prices_text}
{f'Aktive Tranchen:{chr(10)}{tranche_text}' if tranche_text else ''}
{f'Gespeicherte HKCM-Analysen:{chr(10)}{analysen_text}' if analysen_text else ''}
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
        prices_text = format_prices_text(data)
        msg1 = await generate_briefing_msg1(briefing_type, data, prices_text)
        msg2 = await generate_briefing_msg2(briefing_type, data)
        await context.bot.send_message(chat_id=CHAT_ID, text=msg1, disable_web_page_preview=True)
        await context.bot.send_message(chat_id=CHAT_ID, text=msg2, disable_web_page_preview=True)
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
    app.add_handler(CommandHandler("makro", makro_cmd))
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

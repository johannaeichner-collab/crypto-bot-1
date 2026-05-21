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

LERNKARTEN = [
    {"begriff": "Layer 1", "erklaerung": "Layer 1 ist die Basis-Blockchain selbst - zum Beispiel Bitcoin oder Ethereum. Alles andere baut darauf auf.", "beispiel": "Bitcoin (BTC) und Ethereum (ETH) sind Layer 1. Sie sind langsamer aber am sichersten.", "kategorie": "Grundlagen", "frage": "Was ist eine Layer 1 Blockchain?", "antworten": ["A) Eine Blockchain die auf einer anderen aufbaut", "B) Die Basis-Blockchain selbst wie Bitcoin oder Ethereum", "C) Eine Art Wallet"], "richtig": "B"},
    {"begriff": "Layer 2", "erklaerung": "Layer 2 sind Netzwerke die auf einer Layer 1 aufbauen und Transaktionen schneller und guenstiger machen.", "beispiel": "POL (Polygon) ist ein Layer 2 auf Ethereum. Wenn ETH ueberlastet ist, nutzen viele POL.", "kategorie": "Grundlagen", "frage": "Was macht ein Layer 2 Netzwerk?", "antworten": ["A) Es ersetzt Bitcoin", "B) Es macht Transaktionen schneller und guenstiger", "C) Es ist eine neue Wallet"], "richtig": "B"},
    {"begriff": "DeFi", "erklaerung": "DeFi steht fuer Decentralized Finance. Kein Mittelsmann wie eine Bank, alles laeuft ueber Smart Contracts automatisch.", "beispiel": "Du kannst Zinsen verdienen, leihen oder tauschen - ohne Bank, 24/7.", "kategorie": "Konzepte", "frage": "Was bedeutet DeFi?", "antworten": ["A) Digital Finance", "B) Decentralized Finance - Finanzen ohne Mittelsmann", "C) Default Finance"], "richtig": "B"},
    {"begriff": "Smart Contract", "erklaerung": "Ein Smart Contract ist ein selbstausfuehrender Vertrag auf der Blockchain. Regeln sind im Code und werden automatisch ausgefuehrt.", "beispiel": "Wenn Coin X einen Preis erreicht, wird automatisch verkauft - niemand muss das manuell machen.", "kategorie": "Grundlagen", "frage": "Was ist ein Smart Contract?", "antworten": ["A) Ein intelligenter Anwalt", "B) Ein selbstausfuehrender Vertrag im Code der Blockchain", "C) Eine Smartphone App"], "richtig": "B"},
    {"begriff": "Elliott Wellen", "erklaerung": "Die Elliott-Wellen-Theorie besagt dass Maerkte in Mustern schwingen - 5 Impulswellen nach oben, 3 Korrekturwellen nach unten. HKCM nutzt diese Methode.", "beispiel": "HKCM analysiert wo sich BTC gerade in diesem Muster befindet. Welle 3 ist meist die staerkste Bewegung.", "kategorie": "Analyse", "frage": "Was beschreibt die Elliott-Wellen-Theorie?", "antworten": ["A) Meeresstroemungen", "B) Vorhersehbare Kursmuster - 5 Aufwaerts- und 3 Abwaertswellen", "C) Wallet-Sicherheit"], "richtig": "B"},
    {"begriff": "Market Cap", "erklaerung": "Market Cap = Kurs x Anzahl der Coins im Umlauf. Zeigt wie gross ein Coin wirklich ist.", "beispiel": "Ein Coin der 1000 Euro kostet aber nur 1000 Stueck hat ist kleiner als ein Coin der 1 Euro kostet aber eine Milliarde Stueck hat.", "kategorie": "Grundlagen", "frage": "Was ist die Market Cap?", "antworten": ["A) Der aktuelle Kurs", "B) Kurs mal Anzahl aller Coins im Umlauf", "C) Das maximale Limit an Coins"], "richtig": "B"},
    {"begriff": "BTC Dominanz", "erklaerung": "BTC Dominanz zeigt welchen Anteil Bitcoin am gesamten Crypto-Markt hat. Hohe Dominanz = Bitcoin Season. Niedrige Dominanz = Altcoin Season.", "beispiel": "BTC Dominanz 58%: Von 100 Euro in Crypto gehen 58 Euro in Bitcoin. Gut fuer BTC, schlecht fuer Altcoins.", "kategorie": "Markt", "frage": "Was bedeutet eine hohe BTC Dominanz?", "antworten": ["A) Bitcoin steigt stark", "B) Grossteil des Geldes fliesst in Bitcoin, Altcoins verlieren", "C) Viele neue Bitcoins werden gemint"], "richtig": "B"},
    {"begriff": "Fear & Greed Index", "erklaerung": "Misst die Marktstimmung von 0 (extreme Angst) bis 100 (extreme Gier). Kaufe wenn alle Angst haben, verkaufe wenn alle gierig sind.", "beispiel": "Index 15 (extreme Angst) = oft guter Kaufzeitpunkt. Index 90 (extreme Gier) = Markt ueberhitzt.", "kategorie": "Markt", "frage": "Was sagt ein Fear & Greed Index von 20?", "antworten": ["A) Markt ist sehr gierig", "B) Extreme Angst - historisch oft ein Kaufsignal", "C) Index funktioniert nicht"], "richtig": "B"},
    {"begriff": "Widerstand (Resistance)", "erklaerung": "Ein Widerstand ist ein Preislevel wo ein Coin oft stoppt oder zurueckfaellt. Viele Verkaeufer warten dort.", "beispiel": "HKCM nennt fuer RENDER 2.58 und 3.10 Dollar als Widerstaende. Erst wenn diese fallen geht es richtig aufwaerts.", "kategorie": "Analyse", "frage": "Was ist ein Widerstand im Chart?", "antworten": ["A) Technische Stoerung", "B) Preislevel wo viele Verkaeufer warten und der Kurs oft stoppt", "C) Der maximale Preis"], "richtig": "B"},
    {"begriff": "Unterstuetzung (Support)", "erklaerung": "Support ist ein Preislevel wo viele Kaeufer einsteigen und der Kurs abgefedert wird. Faellt ein Coin darunter ist das ein schlechtes Zeichen.", "beispiel": "CRO hat Support bei 0.07 Dollar. Solange der Kurs darueber bleibt ist die Situation stabil.", "kategorie": "Analyse", "frage": "Was passiert wenn ein Coin unter seinen Support faellt?", "antworten": ["A) Er steigt automatisch", "B) Schlechtes Zeichen - der naechste Support wird gesucht", "C) Er wird automatisch gekauft"], "richtig": "B"},
    {"begriff": "DCA", "erklaerung": "Dollar Cost Averaging bedeutet regelmaessig einen fixen Betrag zu investieren - egal ob Kurs hoch oder niedrig. Im Durchschnitt ein fairer Preis.", "beispiel": "Jeden Monat 100 Euro in BTC. Im Crash kaufst du viel, bei hohem Kurs wenig. Ueber Zeit funktioniert das gut.", "kategorie": "Strategie", "frage": "Was ist DCA?", "antworten": ["A) Immer beim Tiefpunkt kaufen", "B) Regelmaessig fixen Betrag investieren unabhaengig vom Kurs", "C) Nur in Dollar investieren"], "richtig": "B"},
    {"begriff": "Tranchen", "erklaerung": "Nicht alles auf einmal investieren, sondern in mehreren Schritten. Risiko wird verteilt.", "beispiel": "BTC bei 80k erste Tranche. Faellt er auf 70k zweite Tranche. Faellt er auf 60k dritte Tranche.", "kategorie": "Strategie", "frage": "Warum kauft man in Tranchen?", "antworten": ["A) Weil nicht genug Geld da ist", "B) Um Risiko zu verteilen und bei fallenden Kursen guenstiger einzukaufen", "C) Weil Exchanges kleine Mengen fordern"], "richtig": "B"},
    {"begriff": "Bull Run", "erklaerung": "Ein Bull Run ist eine starke anhaltende Aufwaertsbewegung. Historisch bei Bitcoin alle 4 Jahre nach dem Halving.", "beispiel": "2020-2021 grosser Bull Run. BTC von 10k auf 69k Dollar. Altcoins wie ADA und LINK stiegen teils 1000 Prozent.", "kategorie": "Markt", "frage": "Was ist ein Bull Run?", "antworten": ["A) Bitcoin faellt auf Tiefpunkt", "B) Starke anhaltende Aufwaertsbewegung im Markt", "C) Viele neue Coins werden erschaffen"], "richtig": "B"},
    {"begriff": "Halving", "erklaerung": "Beim Bitcoin Halving wird die Mining-Belohnung halbiert. Passiert alle 4 Jahre. Weniger neues Angebot - historisch folgte danach immer ein Bull Run.", "beispiel": "Letztes Halving April 2024. Statt 6.25 BTC bekommen Miner jetzt 3.125 BTC. Weniger Angebot bei gleicher Nachfrage.", "kategorie": "Bitcoin", "frage": "Was bewirkt das Bitcoin Halving?", "antworten": ["A) Bitcoin wird schneller", "B) Mining-Belohnung halbiert sich, weniger neue BTC kommen auf den Markt", "C) Preis halbiert sich automatisch"], "richtig": "B"},
    {"begriff": "Altcoin Season", "erklaerung": "Wenn Altcoins stark steigen und besser performen als BTC. Passiert meist nachdem BTC einen Hoechststand erreicht.", "beispiel": "BTC Dominanz unter 45 Prozent = Altcoin Season wahrscheinlich. Dann koennen ADA XRP RENDER stark outperformen.", "kategorie": "Markt", "frage": "Wann ist Altcoin Season?", "antworten": ["A) Wenn neue Altcoins erschaffen werden", "B) Wenn Altcoins besser performen als Bitcoin", "C) Wenn Altcoins auf Jahrestief sind"], "richtig": "B"},
]

pending_quiz = {}

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

def supabase_patch(table, params, data):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}{params}",
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
    supabase_patch("Tranchen", f"?id=eq.{tranche_id}", {"status": "erreicht"})

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

def get_lernkarte_des_tages():
    try:
        result = supabase_get("Lernkarten", "?order=id.desc&limit=1")
        if isinstance(result, list) and result:
            letzte = result[0].get("begriff", "")
            for i, k in enumerate(LERNKARTEN):
                if k["begriff"] == letzte:
                    naechste = LERNKARTEN[(i + 1) % len(LERNKARTEN)]
                    return naechste
        return LERNKARTEN[0]
    except:
        return LERNKARTEN[0]

def save_lernkarte(begriff):
    datum = datetime.now().strftime("%d.%m.%Y")
    supabase_post("Lernkarten", {
        "begriff": begriff,
        "erklaerung": "",
        "beispiel": "",
        "kategorie": "",
        "letzte_wiederholung": datum,
        "naechste_wiederholung": datum,
        "richtig": "0",
        "falsch": "0"
    })

def update_lernkarte_score(begriff, richtig):
    try:
        result = supabase_get("Lernkarten", f"?begriff=eq.{begriff}&order=id.desc&limit=1")
        if isinstance(result, list) and result:
            eintrag = result[0]
            r = int(eintrag.get("richtig", "0") or "0")
            f = int(eintrag.get("falsch", "0") or "0")
            if richtig:
                r += 1
            else:
                f += 1
            supabase_patch("Lernkarten", f"?id=eq.{eintrag['id']}", {"richtig": str(r), "falsch": str(f)})
    except:
        pass

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
            "https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1d&range=1d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = r.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        prev = data["chart"]["result"][0]["meta"]["chartPreviousClose"]
        change = ((price - prev) / prev * 100) if prev else None
        return round(float(price), 2), round(float(change), 2) if change else None
    except:
        return None, None

def get_economic_calendar():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
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

def get_crypto_news():
    feeds = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("Reuters", "https://feeds.reuters.com/reuters/technologyNews"),
        ("Decrypt", "https://decrypt.co/feed"),
    ]
    articles = []
    keywords = ["bitcoin", "crypto", "btc", "ethereum", "blockchain", "sec", "etf",
                "fed", "regulation", "reserve", "eu", "clarity", "congress",
                "iran", "geopolit", "trump", "powell"]
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
                    articles.append({"title": title, "link": link, "desc": desc, "source": source})
                    break
        except:
            continue
        if len(articles) >= 3:
            break
    return articles[:3]

def summarize_article(title, desc, link):
    prompt = f"""Fasse diesen Artikel in 4-5 Saetzen auf Deutsch zusammen. Erklaere was passiert ist und was das konkret fuer den Crypto-Markt bedeutet.

Titel: {title}
Inhalt: {desc}

Schreibe verstaendlich - kein Fachjargon ohne Erklaerung."""
    return ask_ai("Du bist ein Finanzjournalist. Fasse Artikel klar zusammen.", prompt)

async def generate_briefing_msg1(briefing_type, prices_data, prices_text):
    btc = prices_data.get("bitcoin", {})
    eth = prices_data.get("ethereum", {})
    fg_value, fg_label = get_fear_greed()
    btc_dom = get_btc_dominance()
    oil_price, oil_change = get_oil_price()
    heute = datetime.now().strftime("%d.%m.%Y %H:%M")

    btc_chg = btc.get("usd_24h_change", 0) or 0
    eth_chg = eth.get("usd_24h_change", 0) or 0

    altcoin_lines = []
    for coin_id, sym in COINS.items():
        if sym in ["BTC", "ETH"]:
            continue
        d = prices_data.get(coin_id, {})
        chg = d.get("usd_24h_change", 0) or 0
        price = d.get("usd", 0) or 0
        diff = chg - btc_chg
        if diff > 1:
            status = "staerker als BTC"
        elif diff < -1:
            status = "schwaecher als BTC"
        else:
            status = "aehnlich wie BTC"
        altcoin_lines.append(f"{sym}: {format_price(price)} ({chg:+.1f}%) - {status}")

    oil_str = "nicht verfuegbar"
    if oil_price:
        oil_chg_str = f" ({oil_change:+.1f}%)" if oil_change is not None else ""
        oil_str = f"${oil_price}{oil_chg_str}"

    fg_str = f"{fg_value}/100 ({fg_label})" if fg_value else "nicht verfuegbar"
    dom_str = f"{btc_dom}%" if btc_dom else "nicht verfuegbar"

    prompt = f"""Erstelle Nachricht 1 des {briefing_type} fuer Johanna. Heute: {heute}

BITCOIN: {format_price(btc.get('usd', 0))} ({btc_chg:+.1f}%)
ETHEREUM: {format_price(eth.get('usd', 0))} ({eth_chg:+.1f}%)

ALLE ALTCOINS:
{chr(10).join(altcoin_lines)}

MAKRO:
Fear & Greed: {fg_str}
BTC Dominanz: {dom_str}
Oelpreis: {oil_str}

Formatiere so:

MARKT {briefing_type.upper()} - {heute}

BTC Bitcoin
[2-3 Saetze: Kursbewegung erklaeren, wichtige Preislevels]

ETH Ethereum
[2 Saetze: Kursbewegung, Verhaeltnis zu BTC]

ALTCOIN-LAGE
BTC Dominanz {dom_str} - [erklaere ob Bitcoin Season oder Altcoin Season]
Staerker als BTC: [Liste]
Aehnlich wie BTC: [Liste]
Schwaecher als BTC: [Liste]

MARKTSTIMMUNG
Fear & Greed: {fg_str} - [erklaere was das bedeutet]
Oelpreis: {oil_str} - [erklaere Zusammenhang mit Crypto]

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
            actual = f" | Ergebnis: {e['actual']}" if e['actual'] else " | Ergebnis ausstehend"
            forecast = f" | Prognose: {e['forecast']}" if e['forecast'] else ""
            calendar_lines.append(f"{e['date'][:10]} - {e['event']}{actual}{forecast}")
        calendar_text = "\n".join(calendar_lines)

    tranche_text = "\n".join([f"- {t['coin']}: Ziel ${t['zielpreis']}" for t in tranchen]) if tranchen else "Keine"

    prompt = f"""Erstelle Nachricht 2 des {briefing_type} fuer Johanna. Heute: {heute}

NEWS:
{chr(10).join(news_summaries)}

WIRTSCHAFTSKALENDER:
{calendar_text if calendar_text else "Keine wichtigen Termine"}

HKCM-ANALYSEN:
{analysen_text[:800] if analysen_text else "Keine gespeichert"}

AKTIVE TRANCHEN:
{tranche_text}

Formatiere so:

TOP NEWS

1. [Titel]
[4-5 Saetze was passiert ist und warum wichtig]
Bedeutung fuer Crypto: [1 Satz]
Quelle: [Name] | [Link]

2. [gleich]

3. [gleich]

WIRTSCHAFTSKALENDER
[Vorwarnungen fuer morgen/uebermorgen mit Erklaerung was der Termin bedeutet]
[Heutige Ergebnisse mit Bedeutung fuer Crypto]

HKCM-CHECK
[Welche Coins naehern sich Kauf- oder Verkaufszonen?]

HANDLUNGSHINWEISE
[2-3 konkrete Punkte]

Max 400 Woerter. Auf Deutsch."""

    system = "Du bist Johannas Crypto-Assistent. Informiere detailliert aber verstaendlich."
    return ask_ai(system, prompt)

def generate_lernkarte_msg(karte):
    save_lernkarte(karte["begriff"])
    return f"""LERNKARTE DES TAGES

Begriff: {karte['begriff']}
Kategorie: {karte['kategorie']}

Was ist das?
{karte['erklaerung']}

Beispiel:
{karte['beispiel']}

Teste dich morgen mit /quiz!"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hallo Johanna! Ich bin dein Crypto-Assistent.\n\n"
        "Befehle:\n"
        "/preise - Aktuelle Kurse\n"
        "/mittag - Mittags-Briefing\n"
        "/abend - Abend-Briefing\n"
        "/makro - Makro-Update mit News\n"
        "/lernkarte - Begriff des Tages\n"
        "/quiz - Teste dein Wissen\n"
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

async def lernkarte_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        karte = get_lernkarte_des_tages()
        msg = generate_lernkarte_msg(karte)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = supabase_get("Lernkarten", "?order=id.desc&limit=5")
        if not isinstance(result, list) or not result:
            await update.message.reply_text("Noch keine Lernkarten. Starte mit /lernkarte!")
            return

        import random
        letzter_begriff = result[0].get("begriff", "")
        karte = next((k for k in LERNKARTEN if k["begriff"] == letzter_begriff), None)
        if not karte:
            karte = random.choice(LERNKARTEN)

        pending_quiz[str(update.effective_chat.id)] = karte["richtig"]

        msg = f"QUIZ\n\n{karte['frage']}\n\n"
        for a in karte["antworten"]:
            msg += f"{a}\n"
        msg += "\nAntworte mit A, B oder C!"
        await update.message.reply_text(msg)
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
                fg_erkl = "Gier - Markt laeuft gut, Vorsicht"
            else:
                fg_erkl = "Extreme Gier - Markt ueberhitzt"
            lines.append(f"Fear & Greed: {fg_value}/100 ({fg_label})\n-> {fg_erkl}\n")

        if btc_dom is not None:
            if btc_dom > 55:
                dom_erkl = "Bitcoin Season - Altcoins verlieren"
            elif btc_dom > 45:
                dom_erkl = "Ausgeglichen"
            else:
                dom_erkl = "Altcoin Season moeglich"
            lines.append(f"BTC Dominanz: {btc_dom}%\n-> {dom_erkl}\n")

        if oil_price:
            oil_chg_str = f" ({oil_change:+.1f}%)" if oil_change is not None else ""
            oil_erkl = "Geopolitische Spannung - negativ fuer Risk-Assets" if oil_price > 85 else "Stabil"
            lines.append(f"Oelpreis: ${oil_price}{oil_chg_str}\n-> {oil_erkl}\n")

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
        karte = get_lernkarte_des_tages()
        msg3 = generate_lernkarte_msg(karte)
        await update.message.reply_text(msg1, disable_web_page_preview=True)
        await update.message.reply_text(msg2, disable_web_page_preview=True)
        await update.message.reply_text(msg3)
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
        await update.message.reply_text("Format: /tranche BTC 75000 500")
        return
    coin, zielpreis, betrag = args[0].upper(), args[1], args[2]
    save_tranche(coin, zielpreis, betrag)
    await update.message.reply_text(f"Tranche gespeichert:\n{coin} bei ${zielpreis} fuer EUR{betrag}")

async def tranchen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tranchen = get_tranchen()
        if not tranchen:
            await update.message.reply_text("Noch keine Tranchen.")
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
        user_prompt = f"""HKCM Krypto-Analyse Screenshot. Extrahiere:
- Coin, Datum, Primaerszenario, Alternativszenario
- Unterstuetzungen, Widerstaende, Handelszonen
Einschaetzung basierend auf aktuellem Kurs.
Kurse: {prices_text}"""
        system = "Du bist Johannas Crypto-Assistent. Analysiere HKCM-Screenshots auf Deutsch."
        reply = ask_ai_with_image(system, user_prompt, image_base64)
        coin_symbol = ask_ai("Nur Coin-Symbol antworten.", f"Welcher Coin wird analysiert? {reply[:200]}").strip().upper()
        save_analyse(coin_symbol, reply)
        await update.message.reply_text(reply)
        await update.message.reply_text(f"Analyse fuer {coin_symbol} gespeichert!")
    except Exception as e:
        await update.message.reply_text(f"Fehler: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = str(update.effective_chat.id)

    if chat_id in pending_quiz:
        richtige_antwort = pending_quiz.pop(chat_id)
        antwort = text.strip().upper()
        result = supabase_get("Lernkarten", "?order=id.desc&limit=1")
        letzter_begriff = result[0].get("begriff", "") if isinstance(result, list) and result else ""

        if antwort == richtige_antwort:
            update_lernkarte_score(letzter_begriff, True)
            await update.message.reply_text(f"Richtig! Super! Die Antwort {richtige_antwort} ist korrekt.")
        else:
            update_lernkarte_score(letzter_begriff, False)
            karte = next((k for k in LERNKARTEN if k["begriff"] == letzter_begriff), None)
            erkl = karte["erklaerung"] if karte else ""
            await update.message.reply_text(f"Leider falsch. Richtig waere {richtige_antwort}.\n\n{erkl}\n\nNicht aufgeben - beim naechsten Mal klappt es!")
        return

    await update.message.reply_text("Denke nach...")
    try:
        data = await get_prices()
        prices_text = format_prices_text(data)
        analysen_text = format_analysen()
        tranchen = get_tranchen()
        tranche_text = "\n".join([f"- {t['coin']}: Ziel ${t['zielpreis']}" for t in tranchen]) if tranchen else ""

        if "HKCM" in text.upper():
            coin_symbol = ask_ai("Nur Coin-Symbol.", f"Welcher Coin wird analysiert? {text[:300]}").strip().upper()
            save_analyse(coin_symbol, text)
            await update.message.reply_text(f"Analyse fuer {coin_symbol} gespeichert!")
            return

        system = f"""Du bist Johannas persoenlicher Crypto-Assistent.
Coins: BTC ETH XRP ADA LTC AVAX HBAR CRO POL RENDER VET FET MANA LINK
Preise: {prices_text}
{f'Tranchen:{chr(10)}{tranche_text}' if tranche_text else ''}
{f'HKCM-Analysen:{chr(10)}{analysen_text}' if analysen_text else ''}
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
        if hour == 10:
            karte = get_lernkarte_des_tages()
            msg3 = generate_lernkarte_msg(karte)
            await context.bot.send_message(chat_id=CHAT_ID, text=msg3)
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
    app.add_handler(CommandHandler("lernkarte", lernkarte_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
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

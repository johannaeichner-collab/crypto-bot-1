# Crypto Telegram Bot – Setup

## Umgebungsvariablen (in Railway eintragen)

| Variable | Wert |
|---|---|
| TELEGRAM_TOKEN | Dein Bot-Token von @BotFather |
| CHAT_ID | Deine Telegram-ID (von @userinfobot) |
| ANTHROPIC_API_KEY | Dein Claude API Key |

## Deploy auf Railway

1. Gehe auf railway.app → "New Project" → "Deploy from GitHub repo"
2. Lade diesen Ordner als GitHub Repo hoch (oder nutze Railway CLI)
3. Trage die 3 Umgebungsvariablen ein
4. Bot startet automatisch

## Befehle

- /preise – Live-Kurse
- /mittag – Mittags-Briefing
- /abend – Abend-Briefing  
- /tranche BTC 75000 500 – Tranche anlegen
- /tranchen – Alle Tranchen + Status
- Freitext – Frag den Assistenten alles

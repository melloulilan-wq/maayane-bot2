import os
import asyncio
import httpx
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ── Configuration ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
AGENT_ID          = "agent_01Gij1jRdHhxaWiqyh4YSGAL"
ENVIRONMENT_ID    = "env_01D7tAgLmBSQcnxWGMYcknWW"
TELEGRAM_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]

HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "managed-agents-2026-04-01",
    "content-type": "application/json",
}
BASE_URL = "https://api.anthropic.com/v1"

# ── Envoi d'un message à l'agent et récupération de la réponse ───────────────
async def process_with_agent(message_text: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Créer la session
        r = await client.post(f"{BASE_URL}/sessions", headers=HEADERS, json={
            "agent": AGENT_ID,
            "environment_id": ENVIRONMENT_ID,
            "title": f"Commande {datetime.now().strftime('%d%m%y-%H%M%S')}",
        })
        r.raise_for_status()
        session_id = r.json()["id"]

        # 2. Envoyer le bon de commande
        await client.post(f"{BASE_URL}/sessions/{session_id}/events", headers=HEADERS, json={
            "events": [{"type": "user.message", "content": [{"type": "text", "text": message_text}]}]
        })

        # 3. Attendre la réponse (polling)
        for _ in range(60):  # max 60s
            await asyncio.sleep(2)
            ev = await client.get(f"{BASE_URL}/sessions/{session_id}/events", headers=HEADERS)
            events = ev.json().get("data", [])
            # Chercher le dernier message de l'agent
            agent_msgs = [e for e in events if e.get("type") == "agent.message"]
            idle = [e for e in events if e.get("type") == "session.status_idle"]
            if idle and agent_msgs:
                last = agent_msgs[-1]
                content = last.get("content", [])
                return " ".join(c.get("text", "") for c in content if c.get("type") == "text")

        return "⚠️ Délai dépassé — veuillez réessayer."

# ── Handler Telegram ──────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    text = update.message.text or ""

    await update.message.reply_text(f"⏳ Traitement de votre commande en cours...")
    response = await process_with_agent(text)
    await update.message.reply_text(response)

# ── Lancement du bot ──────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot Telegram démarré...")
    app.run_polling()

if __name__ == "__main__":
    main()

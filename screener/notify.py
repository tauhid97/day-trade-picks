"""MESSENGER BOT - sends messages.

To YOU (Boss), privately on Telegram - set these GitHub secrets:
  TELEGRAM_BOT_TOKEN   (from @BotFather)
  TELEGRAM_CHAT_ID     (your personal ID, from @userinfobot)
To your COMMUNITY (only if COMMUNITY_POSTING = True in config.py):
  DISCORD_WEBHOOK_URL and/or TELEGRAM_COMMUNITY_CHAT_ID
"""
import os

import requests

from . import config as C


def _telegram(chat, text):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not (tok and chat):
        return False
    plain = text.replace("**", "").replace("\n_", "\n").rstrip("_")
    for i in range(0, len(plain), 4000):
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": plain[i:i + 4000],
                                "disable_web_page_preview": True}, timeout=20)
        if not r.ok:
            print("Telegram error:", r.text[:200])
    return True


def to_boss(text):
    return _telegram(os.getenv("TELEGRAM_CHAT_ID"), text)


def to_community(text):
    if not C.COMMUNITY_POSTING:
        return False
    sent = _telegram(os.getenv("TELEGRAM_COMMUNITY_CHAT_ID"), text)
    hook = os.getenv("DISCORD_WEBHOOK_URL")
    if hook:
        for i in range(0, len(text), 1900):
            requests.post(hook, json={"content": text[i:i + 1900]}, timeout=20)
        sent = True
    return sent

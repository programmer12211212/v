"""VIA AI: OpenRouter API bilan ishlaydi."""
import json
import urllib.error
import urllib.request

from django.conf import settings

SYSTEM = (
    "Sen VIA AI — VIA ijtimoiy ilovasining yordamchisisan. O'zbek tilida, qisqa va aniq javob ber. "
    "Post g'oyalari, startap, biznes, rejalashtirish va umumiy huquqiy savollarda yordam ber. "
    "Huquqiy savollarda aniq holat uchun yurist bilan maslahatlashishni eslat."
)


def is_live():
    return bool(getattr(settings, "OPENROUTER_API_KEY", ""))


def _openrouter_reply(history, message):
    msgs = []
    for text, mine in list(history)[-12:] + [(message, True)]:
        role = "user" if mine else "assistant"
        content = text.strip()
        if not content:
            continue
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + content
        else:
            msgs.append({"role": role, "content": content})

    body = json.dumps({
        "model": settings.OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": SYSTEM}] + msgs,
        "temperature": 0.4,
        "max_tokens": 600,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings.OPENROUTER_API_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))

    choices = data.get("choices", [])
    if not choices:
        raise ValueError("OpenRouter javob bermadi")

    msg = choices[0].get("message", {})
    return str(msg.get("content", "") or "").strip()


def _error_text(exc):
    if isinstance(exc, urllib.error.HTTPError):
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code in (400, 404):
            return (
                "OpenRouter API key yoki model nomi noto'g'ri. "
                "API keyni tekshiring yoki modelni o'zgartiring."
            )
        if exc.code in (401, 403):
            return "OpenRouter API kaliti yaroqsiz yoki ruxsat yo'q."
        if exc.code == 429:
            return "OpenRouter limit tugadi. Bir ozdan keyin qayta urinib ko'ring."
        return f"OpenRouter API xatosi ({exc.code}). {detail[:200]}"
    return "OpenRouter APIga ulanishda tarmoq yoki server xatosi yuz berdi."


def reply(history, message):
    if not is_live():
        return "VIA AI uchun OpenRouter API kaliti topilmadi. settings.py yoki environmentda OPENROUTER_API_KEY ni qo'ying."

    try:
        out = _openrouter_reply(history, message)
        if out:
            return out
        return "VIA AI javob qaytarmadi. Iltimos, keyinroq urinib ko'ring."
    except Exception as exc:
        return _error_text(exc)


def rule_reply(q):
    return "VIA AI demo rejimi o'chirilgan. Gemini API kaliti mavjud bo'lishi kerak."

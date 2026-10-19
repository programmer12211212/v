import re

from django.utils import timezone

WD = ["Du", "Se", "Chor", "Pay", "Ju", "Sha", "Yak"]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
USERNAME = re.compile(r"^[A-Za-z0-9_.]{3,20}$")


def ago(dt):
    """Post vaqti: 'Hozirgina', '5 daqiqa oldin', '2 soat oldin', ..."""
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:
        return "Hozirgina"
    if s < 3600:
        return f"{s // 60} daqiqa oldin"
    if s < 86400:
        return f"{s // 3600} soat oldin"
    if s < 7 * 86400:
        return f"{s // 86400} kun oldin"
    return timezone.localtime(dt).strftime("%d.%m.%Y")


def short_ago(dt):
    """Bildirishnoma vaqti: 'Hozir', '2 daq', '3 soat', 'Kecha', '4 kun'."""
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:
        return "Hozir"
    if s < 3600:
        return f"{s // 60} daq"
    if s < 86400:
        return f"{s // 3600} soat"
    if s < 2 * 86400:
        return "Kecha"
    if s < 14 * 86400:
        return f"{s // 86400} kun"
    return timezone.localtime(dt).strftime("%d.%m")


def chat_label(dt):
    """Xabarlar ro'yxatidagi vaqt: '14:02', 'Kecha', 'Du', '03.10'."""
    d = timezone.localtime(dt)
    diff = (timezone.localdate() - d.date()).days
    if diff <= 0:
        return d.strftime("%H:%M")
    if diff == 1:
        return "Kecha"
    if diff < 7:
        return WD[d.weekday()]
    return d.strftime("%d.%m")

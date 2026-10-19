"""Demo ma'lumotlar: dizayndagi boshlang'ich kontent bazaga shu yerdan tushadi."""
import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Chat, Message, Notification, Post, Profile, Reel, StoryItem,
)

GR = [
    "linear-gradient(135deg,#2c4272,#1b2a44)",
    "linear-gradient(135deg,#7a3cff,#ff3b5c)",
    "linear-gradient(135deg,#0f9b8e,#1b2a44)",
    "linear-gradient(135deg,#f59e0b,#ef4444)",
]

DEMO = [  # (username, ko'rinadigan nom)
    ("founderscafe.inc", "founderscafe.inc"),
    ("startap.uz", "startap.uz"),
    ("wentric", "Wentric Learning"),
    ("jamoa", "Jamoa | Startap"),
]

FILLER = [
    "Biznes — bu marafon.", "Birinchi mijoz eng qiyini.", "Huquqiy asos — poydevor.",
    "Jamoa — eng katta kapital.", "Kichik qadamlar, katta natija.", "Xato qilish — o'rganish.",
    "Vaqt eng qimmat resurs.", "Mijoz fikri — oltin.", "Rejasiz maqsad — orzu.",
    "Sabr va izchillik.", "Savdo — ishonch san'ati.", "O'rganishda davom eting.",
]

REPLIES = ["Tushunarli, rahmat!", "Yaxshi, keyinroq gaplashamiz.", "Zo'r g'oya, davom eting!", "Albatta, bajaramiz."]


def ensure_demo():
    if Profile.objects.filter(is_demo=True).exists():
        return
    try:
        with transaction.atomic():
            now = timezone.now()
            P = {}
            for un, name in DEMO:
                P[un] = Profile.objects.create(un=un, name=name, is_demo=True)

            Post.objects.create(
                author=P["founderscafe.inc"], caption="Ba'zan rad etilish — eng katta boshlanish.",
                base_likes=2431, created=now - timedelta(hours=2),
                slides=[
                    "Airbnb ilk $20,000 sarmoyasini olishidan oldin 7 investor tomonidan rad etilgan.",
                    "Ular qo'l qovushtirmadi. Ular davom etishdi.",
                    "Sizning navbatingiz.",
                ],
            )
            Post.objects.create(
                author=P["startap.uz"], caption="Bugungi maslahat: mijozdan boshlang.",
                base_likes=918, created=now - timedelta(hours=5),
                slides=["Mahsulot emas, muammo muhim.", "Avval 10 ta mijoz bilan gaplashing."],
            )

            Reel.objects.create(author=P["founderscafe.inc"], caption="Har bir katta kompaniya kichik boshlangan.",
                                base_likes=12400, bg=GR[1], text="Kichik boshlang.", created=now - timedelta(hours=1))
            Reel.objects.create(author=P["startap.uz"], caption="10 ta mijoz bilan gaplashing.",
                                base_likes=3210, bg=GR[2], text="Avval mijoz, keyin mahsulot.", created=now - timedelta(hours=2))
            Reel.objects.create(author=P["wentric"], caption="Biznes va huquq birga.",
                                base_likes=845, bg=GR[3], text="Huquq + Biznes", created=now - timedelta(hours=3))

            stories = {
                "founderscafe.inc": [("Airbnb 7 marta rad etilgan.", GR[1]), ("Ular davom etishdi.", GR[0])],
                "startap.uz": [("Bugun: mijozdan boshlang.", GR[2])],
                "wentric": [("Yangi kurs yuklandi!", GR[3])],
                "jamoa": [("Ertaga 14:45 da yig'ilish.", GR[0])],
            }
            for un, items in stories.items():
                for tx, bg in items:
                    StoryItem.objects.create(author=P[un], kind="text", text=tx, bg=bg)
    except IntegrityError:
        # Boshqa so'rov bir vaqtda yaratib bo'lgan — muammo emas
        pass


def seed_user(profile):
    """Yangi foydalanuvchi uchun: xabarlar, bildirishnomalar, profil postlari."""
    now = timezone.now()

    chats_def = [
        ("Jamoa | Startap", 1, timedelta(minutes=8), [
            ("Ertaga 14:45 da yig'ilish bor, tayyormisiz?", False),
            ("Ha, taqdimotni tayyorladim.", True),
            ("Zo'r, kutamiz!", False),
        ]),
        ("founderscafe.inc", 0, timedelta(days=1), [("Postingiz juda yoqdi!", False)]),
        ("startap.uz", 2, timedelta(days=3), [("Hamkorlik haqida gaplashsak bo'ladimi?", False)]),
        ("Wentric Learning", 0, timedelta(days=5), [("Yangi kurs materiallari yuklandi.", False)]),
    ]
    chats = {}
    for name, unread, back, msgs in chats_def:
        c = Chat.objects.create(owner=profile, name=name, unread=unread, created=now - back)
        chats[name] = c
        for i, (text, mine) in enumerate(msgs):
            Message.objects.create(chat=c, text=text, mine=mine,
                                   created=now - back + timedelta(minutes=i))

    notes = [
        ("founderscafe.inc", "postingizni yoqtirdi", "home", True, timedelta(minutes=2)),
        ("startap.uz", "sizga xabar yubordi", f"chat:{chats['startap.uz'].id}", True, timedelta(hours=1)),
        ("Wentric Learning", "sizni kuzata boshladi", "me", False, timedelta(hours=3)),
        ("VIA | Eslatma", "Ertaga 14:45 da Jamoangiz bilan yig'ilish", "home", False, timedelta(hours=26)),
    ]
    for title, text, target, unread, back in notes:
        Notification.objects.create(profile=profile, title=title, text=text, target=target,
                                    unread=unread, created=now - back)

    for i, t in enumerate(FILLER):
        Post.objects.create(author=profile, caption="", slides=[t], in_feed=False,
                            created=now - timedelta(days=1 + i))


def random_reply():
    return random.choice(REPLIES)

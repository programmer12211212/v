# VIA — Django backend

`V.html` dizayni **o'zgarmagan** (CSS va HTML bir xil). Faqat JavaScript'dagi ma'lumot manbalari
va tugma amallari Django API'ga ulangan.

## Ishga tushirish

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py runserver
```

Brauzerda: http://127.0.0.1:8000/

Admin panel uchun (ixtiyoriy): `python manage.py createsuperuser` → http://127.0.0.1:8000/admin/

## Nima ulangan

| Funksiya | Endpoint |
|---|---|
| Feed, profil postlari, repostlar, hikoyalar, reels, xabarlar, bildirishnomalar, AI tarixi | `/` (sahifa ichiga joylanadi, flash yo'q) |
| Rasm/video yuklash | `POST /api/media/` |
| Post / Reel joylash | `POST /api/posts/`, `POST /api/reels/` |
| Like, repost | `POST /api/posts|reels/<id>/like|repost/` |
| Izohlar | `GET/POST /api/posts|reels/<id>/comments/` |
| Hikoya qo'shish / ko'rilgan | `POST /api/stories/`, `POST /api/stories/<id>/seen/` |
| Xabar yuborish / o'qildi | `POST /api/chats/<id>/send|read/` |
| VIA AI | `POST /api/ai/` |
| Bildirishnomalar | `POST /api/notifications/<id>/read/`, `.../read-all/` |
| Kuzatish | `POST /api/follow/` |
| Profilni tahrirlash | `PUT /api/profile/` |
| Ilova sozlamalari (fon, xiralik) | `PUT /api/settings/` |
| Obuna rejasi (demo, to'lov yo'q) | `POST /api/plan/` |

## Muhim eslatmalar

- **Login yo'q** (dizaynda login ekrani yo'q): har bir brauzer birinchi kirishda avtomatik akkaunt
  oladi va sessiya cookie orqali eslab qolinadi (5 yil). Cookie o'chirilsa — yangi akkaunt ochiladi.
  Haqiqiy ro'yxatdan o'tish kerak bo'lsa, `core/views.py:create_account` o'rniga Django auth ulash kerak.
- **VIA AI**: `ANTHROPIC_API_KEY` o'rnatilsa Claude javob beradi (`ANTHROPIC_MODEL` bilan model tanlanadi),
  aks holda (yoki xatoda) oflayn qoidalar bilan ishlaydi.
- **Media**: `media/` papkasiga saqlanadi va `/media/...` orqali beriladi (video uchun Range qo'llab-quvvatlanadi).
  Rasm ≤ 15 MB, video ≤ 100 MB. Production'da nginx orqali berish tavsiya etiladi.

## Production

```bash
export DJANGO_DEBUG=0
export DJANGO_SECRET_KEY='uzun-tasodifiy-kalit'
export DJANGO_ALLOWED_HOSTS='sizning-domen.uz'
export DJANGO_CSRF_TRUSTED_ORIGINS='https://sizning-domen.uz'
```
`gunicorn via.wsgi` bilan ishga tushiring (`pip install gunicorn`).

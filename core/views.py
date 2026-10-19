import json
import mimetypes
import os
import re
import uuid
from functools import wraps

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils._os import safe_join
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from . import ai
from .models import (
    AiMessage, Chat, Comment, Follow, Media, Message, Notification, Post, PostLike,
    PostRepost, Profile, Reel, ReelLike, ReelRepost, StoryItem, StorySeen,
)
from .seed import ensure_demo, random_reply, seed_user
from .serializers import (
    build_boot, ser_comment, ser_item, ser_me, ser_note, ser_posts, ser_reels,
)
from .utils import HEX, USERNAME, chat_label

PLANS = {"free", "pro", "premium", "vip", "team"}
BADGES = {f"p{i}" for i in range(1, 7)} | {f"v{i}" for i in range(1, 7)} | {"team"}

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
VIDEO_TYPES = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "video/x-m4v": ".m4v",
}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".m4v"}
MAX_IMAGE = 15 * 1024 * 1024
MAX_VIDEO = 100 * 1024 * 1024


def _safe_name(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    return value


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def err(message, status=400):
    return JsonResponse({"error": message}, status=status)


def body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError("Noto'g'ri so'rov")
    if not isinstance(data, dict):
        raise ApiError("Noto'g'ri so'rov")
    return data


def api(methods):
    def deco(fn):
        @wraps(fn)
        @require_http_methods(methods)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return err("Sessiya tugadi, sahifani yangilang", 401)
            try:
                me = Profile.objects.get(user=request.user)
            except Profile.DoesNotExist:
                return err("Sessiya tugadi, sahifani yangilang", 401)
            try:
                return fn(request, me, *args, **kwargs)
            except ApiError as e:
                return err(str(e), e.status)
            except Exception:
                return err("Serverda nosozlik yuz berdi", 500)

        return wrapper

    return deco


def own_media(me, src, kind):
    if not isinstance(src, str):
        raise ApiError("Noto'g'ri media")
    src = _safe_name(src)
    if not src.startswith(settings.MEDIA_URL):
        raise ApiError("Noto'g'ri media")
    name = src[len(settings.MEDIA_URL):]
    if not name or name.startswith("/") or name.startswith("..") or "/../" in name:
        raise ApiError("Noto'g'ri media")
    m = Media.objects.filter(owner=me, file=name, kind=kind).first()
    if not m:
        raise ApiError("Media topilmadi. Faylni qaytadan yuklang")
    return m


def get_obj(model, pk):
    try:
        return model.objects.select_related("author").get(pk=pk)
    except model.DoesNotExist:
        raise ApiError("Topilmadi", 404)


def new_username():
    base = "imwwk"
    if not Profile.objects.filter(un__iexact=base).exists():
        return base
    for _ in range(50):
        cand = f"{base}{uuid.uuid4().int % 9000 + 1000}"
        if not Profile.objects.filter(un__iexact=cand).exists():
            return cand
    return f"{base}_{uuid.uuid4().hex[:8]}"


def create_account(request, user=None):
    with transaction.atomic():
        fresh = user is None
        if fresh:
            user = User.objects.create(username="via_" + uuid.uuid4().hex[:24])
            user.set_unusable_password()
            user.save()
        profile = Profile.objects.create(
            user=user,
            un=new_username(),
            name="imwwk",
            bio="Founder of Wentric\nLearning business & law",
        )
        seed_user(profile)
    if fresh:
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return profile


@never_cache
@ensure_csrf_cookie
def index(request):
    ensure_demo()
    profile = None
    existing = request.user if request.user.is_authenticated else None
    if existing is not None:
        profile = Profile.objects.filter(user=existing).first()
    if profile is None:
        profile = create_account(request, existing)
    boot = build_boot(profile)
    boot["csrf"] = get_token(request)
    return render(request, "core/index.html", {"boot": boot})


def serve_media(request, path):
    path = _safe_name(path)
    try:
        full = safe_join(settings.MEDIA_ROOT, path)
    except (SuspiciousFileOperation, ValueError):
        raise Http404
    if not os.path.isfile(full):
        raise Http404
    size = os.path.getsize(full)
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if size == 0:
        return HttpResponse(b"", content_type=ctype)

    start, end, status = 0, size - 1, 200
    rng = request.headers.get("Range", "").strip()
    if rng:
        m = re.match(r"^bytes=(\d*)-(\d*)$", rng)
        if m and (m.group(1) or m.group(2)):
            s, e = m.groups()
            if s == "":
                start = max(0, size - int(e))
            else:
                start = int(s)
                if e:
                    end = min(int(e), size - 1)
            if start > end or start >= size:
                resp = HttpResponse(status=416)
                resp["Content-Range"] = f"bytes */{size}"
                return resp
            status = 206
    length = end - start + 1

    def chunks():
        with open(full, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(64 * 1024, left))
                if not data:
                    break
                left -= len(data)
                yield data

    resp = StreamingHttpResponse(chunks(), status=status, content_type=ctype)
    resp["Content-Length"] = str(length)
    resp["Accept-Ranges"] = "bytes"
    resp["Cache-Control"] = "public, max-age=31536000, immutable"
    if status == 206:
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
    return resp


@api(["GET"])
def bootstrap(request, me):
    data = build_boot(me)
    return JsonResponse(data)


@api(["POST"])
def upload_media(request, me):
    f = request.FILES.get("file")
    if not f:
        raise ApiError("Fayl tanlanmagan")
    if f.size <= 0:
        raise ApiError("Bo'sh fayl yuklanmaydi")
    ctype = (f.content_type or "").split(";")[0].strip().lower()
    ext = os.path.splitext(f.name or "")[1].lower()
    if ctype in IMAGE_TYPES:
        kind, ext = "image", IMAGE_TYPES[ctype]
    elif ctype in VIDEO_TYPES:
        kind, ext = "video", VIDEO_TYPES[ctype]
    elif ctype.startswith("video/") and ext in {".mp4", ".mov", ".webm", ".m4v"}:
        kind = "video"
    elif ctype.startswith("image/") and ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        kind = "image"
    else:
        raise ApiError("Bu fayl turi qo'llanmaydi")
    if ext not in ALLOWED_EXT:
        raise ApiError("Bu fayl turi qo'llanmaydi")
    if kind == "image" and f.size > MAX_IMAGE:
        raise ApiError("Rasm 15 MB dan oshmasin")
    if kind == "video" and f.size > MAX_VIDEO:
        raise ApiError("Video 100 MB dan oshmasin")
    m = Media(owner=me, kind=kind, size=f.size)
    m.file.save("x" + ext, f, save=True)
    return JsonResponse({"id": m.id, "kind": kind, "url": m.url})


def clean_slides(me, slides):
    if not isinstance(slides, list) or not 1 <= len(slides) <= 10:
        raise ApiError("1–10 ta slayd bo'lishi kerak")
    out = []
    for s in slides:
        if isinstance(s, str):
            t = s.strip()
            if not t or len(t) > 2000:
                raise ApiError("Matn 1–2000 belgi bo'lishi kerak")
            out.append(t)
        elif isinstance(s, dict) and s.get("k") in ("i", "v"):
            m = own_media(me, s.get("src"), "image" if s["k"] == "i" else "video")
            out.append({"k": s["k"], "src": m.url})
        else:
            raise ApiError("Noto'g'ri slayd")
    return out


@api(["POST"])
def create_post(request, me):
    d = body(request)
    caption = str(d.get("caption") or "").strip()
    if len(caption) > 2200:
        raise ApiError("Izoh juda uzun")
    slides = clean_slides(me, d.get("slides"))
    post = Post.objects.create(author=me, caption=caption, slides=slides)
    note = Notification.objects.create(
        profile=me, title="VIA", text="Postingiz muvaffaqiyatli joylandi", target="home"
    )
    return JsonResponse({"post": ser_posts(me, [post])[0], "note": ser_note(note)})


@api(["POST"])
def create_reel(request, me):
    d = body(request)
    caption = str(d.get("caption") or "").strip()
    if len(caption) > 2200:
        raise ApiError("Izoh juda uzun")
    m = own_media(me, d.get("src"), "video")
    reel = Reel.objects.create(author=me, caption=caption, video=m.url)
    return JsonResponse({"reel": ser_reels(me, [reel])[0]})


def _toggle(d, exists):
    return bool(d["on"]) if "on" in d else not exists


@api(["POST"])
def like_post(request, me, pk):
    post = get_obj(Post, pk)
    d = body(request)
    exists = PostLike.objects.filter(profile=me, post=post).exists()
    if _toggle(d, exists):
        PostLike.objects.get_or_create(profile=me, post=post)
    else:
        PostLike.objects.filter(profile=me, post=post).delete()
    liked = PostLike.objects.filter(profile=me, post=post).exists()
    return JsonResponse({"liked": liked, "count": post.base_likes + post.likes.count()})


@api(["POST"])
def like_reel(request, me, pk):
    reel = get_obj(Reel, pk)
    d = body(request)
    exists = ReelLike.objects.filter(profile=me, reel=reel).exists()
    if _toggle(d, exists):
        ReelLike.objects.get_or_create(profile=me, reel=reel)
    else:
        ReelLike.objects.filter(profile=me, reel=reel).delete()
    liked = ReelLike.objects.filter(profile=me, reel=reel).exists()
    return JsonResponse({"liked": liked, "count": reel.base_likes + reel.likes.count()})


@api(["POST"])
def repost_post(request, me, pk):
    post = get_obj(Post, pk)
    d = body(request)
    exists = PostRepost.objects.filter(profile=me, post=post).exists()
    if _toggle(d, exists):
        PostRepost.objects.get_or_create(profile=me, post=post)
    else:
        PostRepost.objects.filter(profile=me, post=post).delete()
    return JsonResponse({"reposted": PostRepost.objects.filter(profile=me, post=post).exists()})


@api(["POST"])
def repost_reel(request, me, pk):
    reel = get_obj(Reel, pk)
    d = body(request)
    exists = ReelRepost.objects.filter(profile=me, reel=reel).exists()
    if _toggle(d, exists):
        ReelRepost.objects.get_or_create(profile=me, reel=reel)
    else:
        ReelRepost.objects.filter(profile=me, reel=reel).delete()
    return JsonResponse({"reposted": ReelRepost.objects.filter(profile=me, reel=reel).exists()})


def _comments(request, me, post=None, reel=None):
    qs = Comment.objects.filter(post=post, reel=reel).select_related("author")
    if request.method == "GET":
        items = list(qs.order_by("-id")[:200])[::-1]
        return JsonResponse({"items": [ser_comment(c) for c in items]})
    d = body(request)
    text = str(d.get("text") or "").strip()
    if not text or len(text) > 500:
        raise ApiError("Izoh 1–500 belgi bo'lishi kerak")
    c = Comment.objects.create(author=me, post=post, reel=reel, text=text)
    return JsonResponse({"item": ser_comment(c)})


@api(["GET", "POST"])
def post_comments(request, me, pk):
    return _comments(request, me, post=get_obj(Post, pk))


@api(["GET", "POST"])
def reel_comments(request, me, pk):
    return _comments(request, me, reel=get_obj(Reel, pk))


@api(["POST"])
def create_story(request, me):
    d = body(request)
    k = d.get("k")
    if k not in ("i", "v"):
        raise ApiError("Noto'g'ri hikoya")
    m = own_media(me, d.get("src"), "image" if k == "i" else "video")
    item = StoryItem.objects.create(author=me, kind="image" if k == "i" else "video", src=m.url)
    StorySeen.objects.filter(viewer=me, author=me).delete()
    return JsonResponse({"item": ser_item(item)})


@api(["POST"])
def story_seen(request, me, author_id):
    if not Profile.objects.filter(pk=author_id).exists():
        raise ApiError("Topilmadi", 404)
    StorySeen.objects.get_or_create(viewer=me, author_id=author_id)
    return JsonResponse({"ok": True})


@api(["POST"])
def chat_send(request, me, pk):
    try:
        chat = Chat.objects.get(pk=pk, owner=me)
    except Chat.DoesNotExist:
        raise ApiError("Suhbat topilmadi", 404)
    text = str(body(request).get("text") or "").strip()
    if not text or len(text) > 2000:
        raise ApiError("Xabar 1–2000 belgi bo'lishi kerak")
    reply = random_reply()
    with transaction.atomic():
        Message.objects.create(chat=chat, text=text, mine=True)
        last = Message.objects.create(chat=chat, text=reply, mine=False)
        if chat.unread:
            chat.unread = 0
            chat.save(update_fields=["unread"])
    return JsonResponse({"reply": reply, "t": chat_label(last.created)})


@api(["POST"])
def chat_read(request, me, pk):
    Chat.objects.filter(pk=pk, owner=me).update(unread=0)
    return JsonResponse({"ok": True})


@api(["POST"])
def ai_chat(request, me):
    text = str(body(request).get("message") or "").strip()
    if not text or len(text) > 2000:
        raise ApiError("Xabar 1–2000 belgi bo'lishi kerak")
    hist = [(m.text, m.mine) for m in AiMessage.objects.filter(profile=me).order_by("-id")[:12]][::-1]
    reply_text = ai.reply(hist, text)
    with transaction.atomic():
        AiMessage.objects.create(profile=me, text=text, mine=True)
        AiMessage.objects.create(profile=me, text=reply_text, mine=False)
    return JsonResponse({"reply": reply_text})


@api(["POST"])
def note_read(request, me, pk):
    Notification.objects.filter(pk=pk, profile=me).update(unread=False)
    return JsonResponse({"ok": True})


@api(["POST"])
def note_read_all(request, me):
    Notification.objects.filter(profile=me, unread=True).update(unread=False)
    return JsonResponse({"ok": True})


@api(["POST"])
def follow(request, me):
    d = body(request)
    name = str(d.get("name") or "").strip()
    target = Profile.objects.filter(name=name).exclude(pk=me.pk).order_by("id").first()
    if not target:
        raise ApiError("Akkaunt topilmadi", 404)
    if d.get("on"):
        Follow.objects.get_or_create(follower=me, target=target)
    else:
        Follow.objects.filter(follower=me, target=target).delete()
    return JsonResponse({"following": Follow.objects.filter(follower=me, target=target).exists()})


def _color(v, field):
    if v in (None, ""):
        return ""
    if not isinstance(v, str) or not HEX.match(v):
        raise ApiError(f"{field}: noto'g'ri rang")
    return v.lower()


@api(["PUT", "POST"])
def update_profile(request, me):
    d = body(request)
    name = str(d.get("name") or "").strip()
    un = str(d.get("un") or "").strip().lstrip("@")
    bio = str(d.get("bio") or "").strip()
    if not name or len(name) > 60:
        raise ApiError("Ismni kiriting (60 belgigacha)")
    if not USERNAME.match(un):
        raise ApiError("Username: 3–20 belgi (harf, raqam, _ .)")
    if Profile.objects.filter(un__iexact=un).exclude(pk=me.pk).exists():
        raise ApiError("Bu username band")
    if len(bio) > 150:
        raise ApiError("Bio 150 belgidan oshmasin")

    av = d.get("av")
    if av in (None, ""):
        avatar = ""
    elif av == me.avatar:
        avatar = av
    else:
        avatar = own_media(me, av, "image").url

    me.name, me.un, me.bio, me.avatar = name, un, bio, avatar

    premium_vip = me.plan in ("premium", "vip")
    if premium_vip:
        me.profile_bg = _color(d.get("bgc"), "Fon")
        me.ring = _color(d.get("ring"), "Halqa")
    if me.plan in ("premium", "vip", "team"):
        badge = d.get("badge")
        if badge in (None, ""):
            me.badge = ""
        elif badge in BADGES:
            me.badge = badge
        else:
            raise ApiError("Noto'g'ri badge")
    if me.plan == "team":
        team = d.get("team") if isinstance(d.get("team"), dict) else {}
        tag = str(team.get("tag") or "TEAM").upper()[:4] or "TEAM"
        me.team_tag = tag
        me.team_color = _color(team.get("c"), "Badge rangi") or "#5b8def"
    me.save()
    return JsonResponse({"me": ser_me(me)})


@api(["PUT", "POST"])
def update_settings(request, me):
    d = body(request)
    try:
        dim = int(d.get("dim", me.app_dim))
        gl = int(d.get("gl", me.app_blur))
    except (TypeError, ValueError):
        raise ApiError("Noto'g'ri qiymat")
    if not 0 <= dim <= 80 or not 8 <= gl <= 40:
        raise ApiError("Qiymat chegaradan tashqarida")
    bgi = d.get("bgi")
    if bgi in (None, ""):
        image = ""
    elif bgi == me.app_bg_image:
        image = bgi
    else:
        image = own_media(me, bgi, "image").url
    me.app_bg_color = _color(d.get("bgc"), "Fon")
    me.app_bg_image = image
    me.app_dim, me.app_blur = dim, gl
    me.save()
    return JsonResponse({"ok": True})


@api(["POST"])
def set_plan(request, me):
    d = body(request)
    plan = d.get("plan")
    if plan not in PLANS:
        raise ApiError("Noto'g'ri reja")
    seats = me.seats
    if plan == "team":
        try:
            seats = int(d.get("seats", 3))
        except (TypeError, ValueError):
            raise ApiError("Noto'g'ri jamoa hajmi")
        if not 3 <= seats <= 5:
            raise ApiError("Jamoa 3–5 kishidan iborat bo'lishi kerak")
    me.plan, me.seats = plan, seats
    me.save(update_fields=["plan", "seats"])
    return JsonResponse({"me": ser_me(me)})

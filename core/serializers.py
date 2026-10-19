"""Frontend kutgan JSON shaklini quradi (V.html dagi obyektlar bilan bir xil kalitlar)."""
from django.db.models import Count

from . import ai
from .models import (
    AiMessage, Chat, Follow, Notification, Post, PostLike, PostRepost, Profile, Reel,
    ReelLike, ReelRepost, StoryItem, StorySeen,
)
from .utils import ago, chat_label, short_ago


def ser_me(p):
    return {
        "id": p.id,
        "name": p.name,
        "un": p.un,
        "bio": p.bio,
        "av": p.avatar or None,
        "plan": p.plan,
        "seats": p.seats,
        "badge": p.badge or None,
        "team": {"tag": p.team_tag, "c": p.team_color},
        "ring": p.ring or None,
        "bgc": p.profile_bg or None,
    }


def ser_settings(p):
    return {
        "bgc": p.app_bg_color or None,
        "bgi": p.app_bg_image or None,
        "dim": p.app_dim,
        "gl": p.app_blur,
    }


def _counts(model, fk, ids):
    return dict(
        model.objects.filter(**{fk + "__in": ids})
        .values(fk)
        .annotate(n=Count("id"))
        .values_list(fk, "n")
    )


def ser_posts(me, posts):
    posts = list(posts)
    ids = [p.id for p in posts]
    likes = _counts(PostLike, "post_id", ids)
    liked = set(PostLike.objects.filter(profile=me, post_id__in=ids).values_list("post_id", flat=True))
    reposted = set(PostRepost.objects.filter(profile=me, post_id__in=ids).values_list("post_id", flat=True))
    return [
        {
            "id": p.id,
            "u": p.author.un,
            "c": p.caption,
            "t": ago(p.created),
            "l": p.base_likes + likes.get(p.id, 0),
            "liked": p.id in liked,
            "rp": p.id in reposted,
            "own": p.author_id == me.id,
            "s": p.slides,
        }
        for p in posts
    ]


def ser_reels(me, reels):
    reels = list(reels)
    ids = [r.id for r in reels]
    likes = _counts(ReelLike, "reel_id", ids)
    liked = set(ReelLike.objects.filter(profile=me, reel_id__in=ids).values_list("reel_id", flat=True))
    reposted = set(ReelRepost.objects.filter(profile=me, reel_id__in=ids).values_list("reel_id", flat=True))
    out = []
    for r in reels:
        o = {
            "id": r.id,
            "u": r.author.un,
            "c": r.caption,
            "l": r.base_likes + likes.get(r.id, 0),
            "liked": r.id in liked,
            "rp": r.id in reposted,
            "own": r.author_id == me.id,
        }
        if r.video:
            o["src"] = r.video
        else:
            o["bg"] = r.bg
            o["tx"] = r.text
        out.append(o)
    return out


def ser_reposts(me):
    items = []
    for r in PostRepost.objects.filter(profile=me).select_related("post__author"):
        items.append((r.created, r.id, "p", r.post))
    for r in ReelRepost.objects.filter(profile=me).select_related("reel__author"):
        items.append((r.created, r.id, "r", r.reel))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    pm = {o["id"]: o for o in ser_posts(me, [x[3] for x in items if x[2] == "p"])}
    rm = {o["id"]: o for o in ser_reels(me, [x[3] for x in items if x[2] == "r"])}
    return [{"k": k, "o": (pm if k == "p" else rm)[obj.id]} for _, _, k, obj in items]


def ser_item(i):
    if i.kind == "text":
        return {"tx": i.text, "bg": i.bg}
    return {"k": "i" if i.kind == "image" else "v", "src": i.src}


def ser_stories(me):
    seen = set(StorySeen.objects.filter(viewer=me).values_list("author_id", flat=True))
    mine_items = list(StoryItem.objects.filter(author=me).order_by("-id")[:30])[::-1]
    out = [{
        "id": me.id, "n": "Sizning hikoyangiz", "mine": 1,
        "seen": me.id in seen, "items": [ser_item(i) for i in mine_items],
    }]
    authors = (
        Profile.objects.filter(story_items__isnull=False).exclude(id=me.id).distinct().order_by("id")[:20]
    )
    for a in authors:
        items = list(StoryItem.objects.filter(author=a).order_by("-id")[:30])[::-1]
        out.append({"id": a.id, "n": a.name, "seen": a.id in seen, "items": [ser_item(i) for i in items]})
    return out


def ser_chats(me):
    out = []
    for c in Chat.objects.filter(owner=me).prefetch_related("messages"):
        msgs = list(c.messages.all())
        last = msgs[-1].created if msgs else c.created
        out.append({
            "id": c.id, "n": c.name, "t": chat_label(last), "u": c.unread,
            "m": [[m.text, 1 if m.mine else 0] for m in msgs] or [["", 0]],
        })
    return out


def ser_note(n):
    return {"id": n.id, "n": n.title, "x": n.text, "t": short_ago(n.created), "u": 1 if n.unread else 0, "go": n.target}


def ser_comment(c):
    return {"id": c.id, "u": c.author.un, "x": c.text, "t": ago(c.created)}


def build_boot(me):
    feed = Post.objects.filter(in_feed=True).select_related("author").order_by("-created", "-id")[:60]
    mine = Post.objects.filter(author=me).select_related("author").order_by("-created", "-id")
    reels = Reel.objects.select_related("author").order_by("-created", "-id")[:40]
    notes = Notification.objects.filter(profile=me)[:50]
    ai_msgs = list(AiMessage.objects.filter(profile=me).order_by("-id")[:40])[::-1]
    follows = Follow.objects.filter(follower=me).select_related("target")
    return {
        "me": ser_me(me),
        "settings": ser_settings(me),
        "posts": ser_posts(me, feed),
        "mine": ser_posts(me, mine),
        "reels": ser_reels(me, reels),
        "reposts": ser_reposts(me),
        "stories": ser_stories(me),
        "chats": ser_chats(me),
        "notes": [ser_note(n) for n in notes],
        "ai": [[m.text, 1 if m.mine else 0] for m in ai_msgs],
        "ai_live": ai.is_live(),
        "following": [f.target.name for f in follows],
        "stats": {
            "followers": me.followers_base + Follow.objects.filter(target=me).count(),
            "following_base": me.following_base,
        },
    }

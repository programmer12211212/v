import os
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"u/{instance.owner_id}/{uuid.uuid4().hex}{ext}"


class Profile(models.Model):
    """Ilovadagi akkaunt. user=None bo'lsa — demo akkaunt (founderscafe.inc va h.k.)."""

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE, related_name="via")
    un = models.CharField("username", max_length=40, unique=True)
    name = models.CharField(max_length=60)
    bio = models.CharField(max_length=150, blank=True, default="")
    avatar = models.CharField(max_length=300, blank=True, default="")

    plan = models.CharField(max_length=10, default="free")
    seats = models.PositiveSmallIntegerField(default=3)
    badge = models.CharField(max_length=4, blank=True, default="")
    team_tag = models.CharField(max_length=4, default="TEAM")
    team_color = models.CharField(max_length=7, default="#5b8def")
    ring = models.CharField(max_length=7, blank=True, default="")
    profile_bg = models.CharField(max_length=7, blank=True, default="")

    # Ilova sozlamalari (Parametrlar sahifasi)
    app_bg_color = models.CharField(max_length=7, blank=True, default="")
    app_bg_image = models.CharField(max_length=300, blank=True, default="")
    app_dim = models.PositiveSmallIntegerField(default=25)
    app_blur = models.PositiveSmallIntegerField(default=24)

    followers_base = models.PositiveIntegerField(default=128)
    following_base = models.PositiveIntegerField(default=84)

    is_demo = models.BooleanField(default=False)
    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"@{self.un}"


class Media(models.Model):
    KINDS = (("image", "image"), ("video", "video"))
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to=upload_path, max_length=300)
    kind = models.CharField(max_length=5, choices=KINDS)
    size = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now)

    @property
    def url(self):
        return settings.MEDIA_URL + self.file.name.replace("\\", "/")

    def __str__(self):
        return self.file.name


class Post(models.Model):
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="posts")
    caption = models.TextField(blank=True, default="")
    # Frontend bilan bir xil format: ["matn", {"k": "i"|"v", "src": "/media/..."}, ...]
    slides = models.JSONField(default=list)
    base_likes = models.PositiveIntegerField(default=0)
    in_feed = models.BooleanField(default=True)
    created = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"Post#{self.pk} by {self.author}"


class Reel(models.Model):
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reels")
    caption = models.TextField(blank=True, default="")
    video = models.CharField(max_length=300, blank=True, default="")  # /media/... URL
    bg = models.CharField(max_length=200, blank=True, default="")      # demo reel uchun gradient
    text = models.CharField(max_length=200, blank=True, default="")    # demo reel uchun matn
    base_likes = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"Reel#{self.pk} by {self.author}"


class PostLike(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("profile", "post")


class ReelLike(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="likes")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("profile", "reel")


class PostRepost(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reposts")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("profile", "post")


class ReelRepost(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="reposts")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("profile", "reel")


class Comment(models.Model):
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="comments")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="comments")
    reel = models.ForeignKey(Reel, null=True, blank=True, on_delete=models.CASCADE, related_name="comments")
    text = models.CharField(max_length=500)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]


class StoryItem(models.Model):
    KINDS = (("text", "text"), ("image", "image"), ("video", "video"))
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="story_items")
    kind = models.CharField(max_length=5, choices=KINDS)
    text = models.CharField(max_length=300, blank=True, default="")
    bg = models.CharField(max_length=200, blank=True, default="")
    src = models.CharField(max_length=300, blank=True, default="")
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]


class StorySeen(models.Model):
    viewer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="seen_stories")
    author = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="story_viewers")

    class Meta:
        unique_together = ("viewer", "author")


class Follow(models.Model):
    follower = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="following")
    target = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="followers")

    class Meta:
        unique_together = ("follower", "target")


class Chat(models.Model):
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="chats")
    name = models.CharField(max_length=60)
    unread = models.PositiveSmallIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    text = models.TextField()
    mine = models.BooleanField(default=False)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]


class AiMessage(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="ai_messages")
    text = models.TextField()
    mine = models.BooleanField(default=False)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]


class Notification(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=60)
    text = models.CharField(max_length=200)
    target = models.CharField(max_length=20, default="home")  # home | me | chat:<id>
    unread = models.BooleanField(default=True)
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created", "-id"]

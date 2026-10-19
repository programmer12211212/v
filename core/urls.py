from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/bootstrap/", views.bootstrap),
    path("api/media/", views.upload_media),
    path("api/posts/", views.create_post),
    path("api/posts/<int:pk>/like/", views.like_post),
    path("api/posts/<int:pk>/repost/", views.repost_post),
    path("api/posts/<int:pk>/comments/", views.post_comments),
    path("api/reels/", views.create_reel),
    path("api/reels/<int:pk>/like/", views.like_reel),
    path("api/reels/<int:pk>/repost/", views.repost_reel),
    path("api/reels/<int:pk>/comments/", views.reel_comments),
    path("api/stories/", views.create_story),
    path("api/stories/<int:author_id>/seen/", views.story_seen),
    path("api/chats/<int:pk>/send/", views.chat_send),
    path("api/chats/<int:pk>/read/", views.chat_read),
    path("api/ai/", views.ai_chat),
    path("api/notifications/read-all/", views.note_read_all),
    path("api/notifications/<int:pk>/read/", views.note_read),
    path("api/follow/", views.follow),
    path("api/profile/", views.update_profile),
    path("api/settings/", views.update_settings),
    path("api/plan/", views.set_plan),
]

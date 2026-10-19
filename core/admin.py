from django.contrib import admin

from . import models

admin.site.register(models.Profile)
admin.site.register(models.Media)
admin.site.register(models.Post)
admin.site.register(models.Reel)
admin.site.register(models.Comment)
admin.site.register(models.StoryItem)
admin.site.register(models.Chat)
admin.site.register(models.Message)
admin.site.register(models.AiMessage)
admin.site.register(models.Notification)
admin.site.register(models.Follow)

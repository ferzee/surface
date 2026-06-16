from django.contrib import admin
from .models import User, BuddyRequest, Dive, Post, PostLike, Comment, Event, EventParticipant


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'location', 'created_at')
    search_fields = ('username', 'email')


@admin.register(BuddyRequest)
class BuddyRequestAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'status', 'created_at')
    list_filter = ('status',)
    list_editable = ('status',)


@admin.register(Dive)
class DiveAdmin(admin.ModelAdmin):
    list_display = ('user', 'discipline', 'value', 'dive_date', 'location')
    list_filter = ('discipline',)
    search_fields = ('user__username',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'created_at')
    search_fields = ('user__username', 'content')


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('post', 'user')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'content', 'created_at')
    search_fields = ('user__username', 'content')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'discipline', 'event_date', 'location', 'max_participants')
    list_filter = ('discipline',)
    search_fields = ('title', 'creator__username')


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status')
    list_filter = ('status',)

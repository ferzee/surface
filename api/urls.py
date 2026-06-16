from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register', views.register),
    path('auth/login', views.login),
    # Users
    path('users/me/avatar', views.upload_avatar),
    path('users/me', views.me),
    path('users/search', views.search_users),
    path('users/<int:id>', views.get_user),
    # Posts
    path('posts/feed', views.feed),
    path('posts/user/<int:id>', views.user_posts),
    path('posts', views.posts),
    path('posts/<int:id>', views.post_detail),
    path('posts/<int:id>/like', views.like_post),
    path('posts/<int:id>/comments', views.comments),
    # Dives
    path('dives', views.dives),
    path('dives/user/<int:id>', views.user_dives),
    path('dives/<int:id>', views.dive_detail),
    # Buddies
    path('buddies', views.buddies),
    path('buddies/requests', views.buddy_requests_list),
    path('buddies/request/<int:id>', views.buddy_request),
    path('buddies/<int:id>', views.remove_buddy),
    # Events
    path('events', views.events),
    path('events/<int:id>/participate', views.event_participate),
    path('events/<int:id>', views.event_detail),
]

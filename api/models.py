from django.db import models


class User(models.Model):
    username = models.TextField(unique=True)
    email = models.TextField(unique=True)
    password_hash = models.TextField()
    bio = models.TextField(default='')
    location = models.TextField(default='')
    avatar_color = models.CharField(max_length=20, default='#0891b2')
    avatar = models.TextField(default='', blank=True)
    header_color = models.CharField(max_length=20, default='ocean')
    certifications = models.TextField(default='[]', blank=True)
    diving_since = models.IntegerField(null=True, blank=True)
    dive_school = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'users'


class BuddyRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests', db_column='sender_id')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests', db_column='receiver_id')
    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'buddy_requests'
        unique_together = [('sender', 'receiver')]


class Dive(models.Model):
    DISCIPLINES = [('static', 'Static'), ('dynamic', 'Dynamic'), ('depth', 'Depth')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    discipline = models.CharField(max_length=20, choices=DISCIPLINES)
    value = models.FloatField()
    notes = models.TextField(default='')
    dive_date = models.DateField()
    location = models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dives'


class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'posts'


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, db_column='post_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')

    class Meta:
        db_table = 'post_likes'
        unique_together = [('post', 'user')]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, db_column='post_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comments'


class Event(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, db_column='creator_id')
    title = models.TextField()
    description = models.TextField(default='')
    location = models.TextField(default='')
    event_date = models.DateTimeField()
    discipline = models.CharField(max_length=20, null=True, blank=True)
    max_participants = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'events'


class EventParticipant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='event_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    status = models.CharField(max_length=20, default='going')

    class Meta:
        db_table = 'event_participants'
        unique_together = [('event', 'user')]


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', db_column='sender_id')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', db_column='receiver_id')
    content = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'


class Notification(models.Model):
    TYPE_CHOICES = [
        ('buddy_request', 'Buddy Request'),
        ('buddy_accepted', 'Buddy Accepted'),
        ('like', 'Like'),
        ('comment', 'Comment'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', db_column='recipient_id')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='triggered_notifications', db_column='actor_id')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, db_column='post_id')
    buddy_request = models.ForeignKey(BuddyRequest, on_delete=models.SET_NULL, null=True, blank=True, db_column='buddy_request_id')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'

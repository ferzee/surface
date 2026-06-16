from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
import random

from api.models import User, BuddyRequest, Dive, Post, PostLike, Comment, Event, EventParticipant
from api.auth import hash_password


USERS = [
    {
        'username': 'alice',
        'email': 'alice@example.com',
        'bio': 'AIDA 3 freediver. Depth is my meditation. Based in Dahab most of the year.',
        'location': 'Dahab, Egypt',
        'avatar_color': '#0891b2',
    },
    {
        'username': 'ben',
        'email': 'ben@example.com',
        'bio': 'Dynamic specialist. Chasing that elusive 200m. Training partner welcome!',
        'location': 'Barcelona, Spain',
        'avatar_color': '#059669',
    },
    {
        'username': 'caro',
        'email': 'caro@example.com',
        'bio': 'SSI Freediving instructor. Static queen 🤫 Love teaching beginners.',
        'location': 'Tenerife, Spain',
        'avatar_color': '#be185d',
    },
    {
        'username': 'diego',
        'email': 'diego@example.com',
        'bio': 'Competitive depth diver. National record holder in CWT. Open to buddy sessions.',
        'location': 'Gran Canaria, Spain',
        'avatar_color': '#1d4ed8',
    },
    {
        'username': 'eva',
        'email': 'eva@example.com',
        'bio': 'Just discovered freediving last year. Totally hooked. Progress every week!',
        'location': 'Amsterdam, Netherlands',
        'avatar_color': '#7c3aed',
    },
    {
        'username': 'finn',
        'email': 'finn@example.com',
        'bio': 'Spearfisher turned competitor. Depth and dynamic. Nordic cold water diver.',
        'location': 'Bergen, Norway',
        'avatar_color': '#b45309',
    },
    {
        'username': 'test',
        'email': 'test@example.com',
        'bio': 'Test account. Password is "password".',
        'location': 'Somewhere',
        'avatar_color': '#0e7490',
    },
]

DIVES = {
    'alice':  [('depth', 42, 'Blue Hole'), ('depth', 38, 'Blue Hole'), ('depth', 35, 'Blue Hole'),
               ('static', 270, 'Pool Dahab'), ('static', 255, 'Open water'), ('dynamic', 110, 'Pool Dahab')],
    'ben':    [('dynamic', 182, 'Barcelona pool'), ('dynamic', 175, 'Barcelona pool'), ('dynamic', 168, 'Club pool'),
               ('depth', 28, 'Port Olimpic'), ('static', 195, 'Barcelona pool')],
    'caro':   [('static', 385, 'Tenerife pool'), ('static', 361, 'Tenerife pool'), ('static', 340, 'Open water'),
               ('depth', 31, 'El Hierro'), ('dynamic', 95, 'Club pool')],
    'diego':  [('depth', 68, 'Gran Canaria'), ('depth', 61, 'Gran Canaria'), ('depth', 54, 'Lanzarote'),
               ('depth', 48, 'Blue Hole'), ('dynamic', 140, 'Gran Canaria pool'), ('static', 310, 'Gran Canaria pool')],
    'eva':    [('depth', 18, 'Amsterdam lake'), ('depth', 14, 'Zeeland'), ('static', 120, 'Club pool'),
               ('dynamic', 55, 'Club pool')],
    'finn':   [('depth', 35, 'Hardangerfjord'), ('depth', 29, 'Lysefjord'), ('dynamic', 130, 'Bergen pool'),
               ('static', 230, 'Bergen pool')],
    'test':   [('depth', 20, 'Test location'), ('dynamic', 75, 'Pool'), ('static', 180, 'Pool')],
}

POSTS = {
    'alice': [
        "New PB today at the Blue Hole — 42m CWT! The visibility was unreal, you could see the bottom from the surface. Feeling grateful for this sport ✨",
        "Reminder that no dive is worth your life. Always dive with a buddy, always have a safety diver at depth. The ocean will be there tomorrow.",
        "Three years ago I couldn't hold my breath for 90 seconds. Today I hit 4:30 static. If you're a beginner — keep going, the adaptation is real.",
    ],
    'ben': [
        "182m dynamic today! So close to that 200m goal. The walls of the pool were basically a blur. Anyone training dynamic in Barcelona want to buddy up?",
        "Hot take: monofin is overrated for beginners. Get your bifiins technique solid first, it'll make you a better overall freediver.",
        "Recovery week. Yoga, stretching, and way too much pasta. Next week we go again.",
    ],
    'caro': [
        "New static record for one of my students today — 3:20 on their second dive course! Proud instructor moment 🥹 Teaching is the best part of this sport.",
        "Pool session this Saturday in Tenerife, all levels welcome. DM me if you want to join. Bring a buddy!",
        "6:25 static today. Felt easy. Might be time to stop playing it safe and actually push at the next competition.",
    ],
    'diego': [
        "68m today. New personal best. The pressure at that depth is something you never fully get used to — in the best possible way.",
        "Looking for training partners in Gran Canaria. I'm there until end of August, training depth daily. Safety exchange always.",
        "Watched some old Natalia Molchanova footage this morning. What a legend. The grace, the depth, the breath-hold. Truly another level.",
    ],
    'eva': [
        "First time hitting 18m today!! My instructor said my equalization has improved so much. A year ago this felt impossible.",
        "Can anyone recommend good freediving spots near Amsterdam? Heading to the lake this weekend but open to suggestions.",
        "The feeling when everything clicks and you just... sink effortlessly. Had that today for the first time. I finally get why people become obsessed with this.",
    ],
    'finn': [
        "Spearfishing in the Hardangerfjord this weekend. 35m depth, caught dinner, saw a seal. Freediving gives you access to a whole other world.",
        "Cold water training tip: wet your face before the dive. Triggers the mammalian dive reflex faster. Works every time.",
    ],
}

COMMENTS = [
    ('alice', 'ben', 0, "That's incredible Ben! 182m is elite territory. What's your turn technique?"),
    ('caro', 'alice', 0, "42m is amazing! How's your equalization holding up at that depth?"),
    ('ben', 'alice', 0, "Congrats!! Dahab is magical for depth. I need to go back."),
    ('diego', 'caro', 2, "6:25 is serious. You should compete, that would podium at nationals."),
    ('alice', 'caro', 0, "Love seeing instructors share these moments. Your students are lucky!"),
    ('finn', 'eva', 2, "That feeling is everything. Welcome to the obsession 😄"),
    ('ben', 'eva', 1, "Try Zeeland! Really nice viz in summer and good depth for training."),
]

EVENTS_DATA = [
    {
        'creator': 'alice',
        'title': 'Blue Hole Dawn Session',
        'description': 'Early morning depth session at the Blue Hole. All levels welcome, safety lines and lanyard required for below 20m. Bring your own fins.',
        'location': 'Blue Hole, Dahab',
        'discipline': 'depth',
        'max_participants': 8,
        'days_from_now': 12,
        'going': ['ben', 'diego'],
        'maybe': ['finn'],
    },
    {
        'creator': 'caro',
        'title': 'Static Apnea Training Camp',
        'description': 'Three-day static training camp. We\'ll work on relaxation, CO2 tables, and mental preparation. All levels. Accommodation available nearby.',
        'location': 'Santa Cruz de Tenerife',
        'discipline': 'static',
        'max_participants': 12,
        'days_from_now': 28,
        'going': ['alice', 'eva'],
        'maybe': [],
    },
    {
        'creator': 'ben',
        'title': 'Barcelona Dynamic Pool Sunday',
        'description': 'Weekly dynamic session at the 50m pool. We do warm-ups, technique drills, and max efforts. Buddy system always in place.',
        'location': 'Piscina Municipal, Barcelona',
        'discipline': 'dynamic',
        'max_participants': None,
        'days_from_now': 5,
        'going': ['caro', 'eva', 'finn'],
        'maybe': ['diego'],
    },
    {
        'creator': 'diego',
        'title': 'Gran Canaria Depth Weekend',
        'description': 'Open water depth training off the south coast. Safety divers provided for 30m+. Bring wetsuit 5mm minimum, water is 22°C.',
        'location': 'Playa de Amadores, Gran Canaria',
        'discipline': 'depth',
        'max_participants': 6,
        'days_from_now': -7,  # past event
        'going': ['alice', 'finn'],
        'maybe': [],
    },
    {
        'creator': 'finn',
        'title': 'Norway Fjord Freedive',
        'description': 'Cold water adventure in the Hardangerfjord. Dry suit recommended, 8°C water. Stunning scenery, visibility up to 15m. Epic experience.',
        'location': 'Hardangerfjord, Norway',
        'discipline': 'depth',
        'max_participants': 5,
        'days_from_now': 45,
        'going': ['diego'],
        'maybe': ['alice'],
    },
]


class Command(BaseCommand):
    help = 'Seed the database with test data'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Clear existing data before seeding')

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Clearing existing data...')
            EventParticipant.objects.all().delete()
            Event.objects.all().delete()
            Comment.objects.all().delete()
            PostLike.objects.all().delete()
            Post.objects.all().delete()
            Dive.objects.all().delete()
            BuddyRequest.objects.all().delete()
            User.objects.all().delete()

        pw_hash = hash_password('password')
        now = timezone.now()
        today = date.today()

        # Users
        users = {}
        for i, u in enumerate(USERS):
            obj, created = User.objects.get_or_create(
                username=u['username'],
                defaults={
                    'email': u['email'],
                    'password_hash': pw_hash,
                    'bio': u['bio'],
                    'location': u['location'],
                    'avatar_color': u['avatar_color'],
                },
            )
            users[u['username']] = obj
            if created:
                self.stdout.write(f"  Created user: {u['username']}")

        # Buddy relationships (a web of accepted connections)
        buddy_pairs = [
            ('alice', 'ben'), ('alice', 'caro'), ('alice', 'diego'),
            ('ben', 'caro'), ('ben', 'eva'), ('ben', 'finn'),
            ('caro', 'diego'), ('caro', 'eva'),
            ('diego', 'finn'),
            ('eva', 'finn'),
            ('test', 'alice'),
        ]
        for sender_name, receiver_name in buddy_pairs:
            BuddyRequest.objects.get_or_create(
                sender=users[sender_name],
                receiver=users[receiver_name],
                defaults={'status': 'accepted'},
            )

        # Pending request
        BuddyRequest.objects.get_or_create(
            sender=users['test'],
            receiver=users['ben'],
            defaults={'status': 'pending'},
        )

        self.stdout.write('  Created buddy relationships')

        # Dives
        for username, dives in DIVES.items():
            user = users[username]
            for i, (discipline, value, location) in enumerate(dives):
                days_ago = random.randint(1, 120)
                Dive.objects.get_or_create(
                    user=user,
                    discipline=discipline,
                    value=value,
                    location=location,
                    defaults={'dive_date': today - timedelta(days=days_ago)},
                )
        self.stdout.write('  Created dives')

        # Posts
        post_objects = {}
        for username, contents in POSTS.items():
            user = users[username]
            post_objects[username] = []
            for i, content in enumerate(contents):
                hours_ago = random.randint(1, 72)
                post, created = Post.objects.get_or_create(
                    user=user,
                    content=content,
                    defaults={},
                )
                if created:
                    Post.objects.filter(pk=post.pk).update(
                        created_at=now - timedelta(hours=hours_ago + i * 8)
                    )
                post_objects[username].append(post)

        self.stdout.write('  Created posts')

        # Likes
        like_map = [
            ('ben', 'alice', 0), ('caro', 'alice', 0), ('diego', 'alice', 0), ('eva', 'alice', 0),
            ('alice', 'ben', 0), ('finn', 'ben', 0),
            ('alice', 'caro', 2), ('diego', 'caro', 2), ('ben', 'caro', 2),
            ('alice', 'diego', 0), ('finn', 'diego', 0),
            ('caro', 'eva', 2), ('ben', 'eva', 2), ('finn', 'eva', 2),
            ('alice', 'finn', 0), ('diego', 'finn', 0),
        ]
        for liker, author, post_idx in like_map:
            posts_for_author = post_objects.get(author, [])
            if post_idx < len(posts_for_author):
                PostLike.objects.get_or_create(
                    post=posts_for_author[post_idx],
                    user=users[liker],
                )
        self.stdout.write('  Created likes')

        # Comments
        for commenter, author, post_idx, content in COMMENTS:
            posts_for_author = post_objects.get(author, [])
            if post_idx < len(posts_for_author):
                Comment.objects.get_or_create(
                    post=posts_for_author[post_idx],
                    user=users[commenter],
                    content=content,
                )
        self.stdout.write('  Created comments')

        # Events
        for ev in EVENTS_DATA:
            creator = users[ev['creator']]
            event_dt = now + timedelta(days=ev['days_from_now'])
            event, created = Event.objects.get_or_create(
                creator=creator,
                title=ev['title'],
                defaults={
                    'description': ev['description'],
                    'location': ev['location'],
                    'discipline': ev['discipline'],
                    'max_participants': ev['max_participants'],
                    'event_date': event_dt,
                },
            )
            for name in ev.get('going', []):
                EventParticipant.objects.get_or_create(
                    event=event, user=users[name], defaults={'status': 'going'}
                )
            for name in ev.get('maybe', []):
                EventParticipant.objects.get_or_create(
                    event=event, user=users[name], defaults={'status': 'maybe'}
                )

        self.stdout.write('  Created events')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {len(USERS)} users seeded. Log in with any username and password "password".'
        ))

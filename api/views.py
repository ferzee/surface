import json
import mimetypes
import os
import random
from functools import wraps
from pathlib import Path

from django.db import connection
from django.db.models import Max, Q
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .auth import check_password, create_token, hash_password, verify_token
from .models import (BuddyRequest, Comment, Dive, Event, EventParticipant,
                     Post, PostLike, User)

COLORS = ['#0891b2', '#0e7490', '#1d4ed8', '#7c3aed', '#059669', '#b45309', '#be185d']
PUBLIC_DIR = Path(__file__).resolve().parent.parent / 'public'


# ── Helpers ──────────────────────────────────────────────────────────────────

def body(request):
    try:
        return json.loads(request.body) if request.body else {}
    except Exception:
        return {}


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth[7:] if auth.startswith('Bearer ') else None
        user_id = verify_token(token)
        if not user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        if not User.objects.filter(id=user_id).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        request.user_id = user_id
        return view_func(request, *args, **kwargs)
    return wrapper


def user_dict(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'bio': user.bio,
        'location': user.location,
        'avatar_color': user.avatar_color,
        'created_at': user.created_at.isoformat() if user.created_at else None,
    }


def rows_as_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── Static file serving ───────────────────────────────────────────────────────

def serve_public(request, filepath='index.html'):
    path = PUBLIC_DIR / filepath
    if not path.exists() or not path.is_file():
        raise Http404
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(open(path, 'rb'), content_type=mime or 'text/plain')


# ── Auth ─────────────────────────────────────────────────────────────────────

@csrf_exempt
def register(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = body(request)
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not username or not email or not password:
        return JsonResponse({'error': 'All fields required'}, status=400)
    if len(password) < 6:
        return JsonResponse({'error': 'Password must be at least 6 characters'}, status=400)
    try:
        user = User.objects.create(
            username=username, email=email,
            password_hash=hash_password(password),
            avatar_color=random.choice(COLORS),
        )
        return JsonResponse({'token': create_token(user.id), 'user': user_dict(user)})
    except Exception as e:
        msg = str(e)
        error = 'Username or email already taken' if 'UNIQUE' in msg else 'Could not create account'
        return JsonResponse({'error': error}, status=400)


@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = body(request)
    identifier = (data.get('email') or '').strip()
    password = data.get('password') or ''
    try:
        user = User.objects.get(email=identifier.lower())
    except User.DoesNotExist:
        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid email/username or password'}, status=401)
    if not check_password(password, user.password_hash):
        return JsonResponse({'error': 'Invalid email/username or password'}, status=401)
    return JsonResponse({'token': create_token(user.id), 'user': user_dict(user)})


# ── Users ─────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def me(request):
    if request.method == 'GET':
        user = User.objects.get(id=request.user_id)
        return JsonResponse(user_dict(user))
    if request.method == 'PUT':
        data = body(request)
        User.objects.filter(id=request.user_id).update(
            bio=data.get('bio') or '',
            location=data.get('location') or '',
        )
        user = User.objects.get(id=request.user_id)
        return JsonResponse(user_dict(user))
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_auth
def search_users(request):
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse([], safe=False)
    users = User.objects.filter(username__icontains=q).exclude(id=request.user_id)[:10]
    return JsonResponse([{
        'id': u.id, 'username': u.username, 'bio': u.bio,
        'location': u.location, 'avatar_color': u.avatar_color,
    } for u in users], safe=False)


@require_auth
def get_user(request, id):
    try:
        user = User.objects.get(id=id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    rel = BuddyRequest.objects.filter(
        Q(sender_id=request.user_id, receiver_id=id) |
        Q(sender_id=id, receiver_id=request.user_id)
    ).first()

    records = {
        d: Dive.objects.filter(user_id=id, discipline=d).aggregate(v=Max('value'))['v']
        for d in ('static', 'dynamic', 'depth')
    }
    buddy_count = BuddyRequest.objects.filter(
        Q(sender_id=id) | Q(receiver_id=id), status='accepted'
    ).count()
    dive_count = Dive.objects.filter(user_id=id).count()

    rel_data = None
    if rel:
        rel_data = {'id': rel.id, 'status': rel.status, 'sender_id': rel.sender_id}

    return JsonResponse({
        **user_dict(user),
        'buddyRelation': rel_data,
        'records': records,
        'buddyCount': buddy_count,
        'diveCount': dive_count,
    })


# ── Posts ─────────────────────────────────────────────────────────────────────

POSTS_SELECT = """
    SELECT p.id, p.user_id, p.content, p.created_at,
           u.username, u.avatar_color,
           (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) AS like_count,
           (SELECT COUNT(*) FROM comments   WHERE post_id=p.id) AS comment_count,
           (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id AND user_id=%s) AS user_liked
    FROM posts p JOIN users u ON p.user_id=u.id
"""


@require_auth
def feed(request):
    uid = request.user_id
    sql = POSTS_SELECT + """
        WHERE p.user_id=%s OR p.user_id IN (
            SELECT CASE WHEN sender_id=%s THEN receiver_id ELSE sender_id END
            FROM buddy_requests
            WHERE (sender_id=%s OR receiver_id=%s) AND status='accepted'
        )
        ORDER BY p.created_at DESC LIMIT 100
    """
    with connection.cursor() as cur:
        cur.execute(sql, [uid, uid, uid, uid, uid])
        posts = rows_as_dicts(cur)
    for p in posts:
        p['user_liked'] = bool(p['user_liked'])
    return JsonResponse(posts, safe=False)


@require_auth
def user_posts(request, id):
    uid = request.user_id
    sql = POSTS_SELECT + "WHERE p.user_id=%s ORDER BY p.created_at DESC"
    with connection.cursor() as cur:
        cur.execute(sql, [uid, id])
        posts = rows_as_dicts(cur)
    for p in posts:
        p['user_liked'] = bool(p['user_liked'])
    return JsonResponse(posts, safe=False)


@csrf_exempt
@require_auth
def posts(request):
    if request.method == 'POST':
        data = body(request)
        content = (data.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Content required'}, status=400)
        post = Post.objects.create(user_id=request.user_id, content=content)
        uid = request.user_id
        sql = POSTS_SELECT + "WHERE p.id=%s"
        with connection.cursor() as cur:
            cur.execute(sql, [uid, post.id])
            result = rows_as_dicts(cur)[0]
        result['user_liked'] = False
        return JsonResponse(result)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@require_auth
def post_detail(request, id):
    if request.method == 'DELETE':
        deleted, _ = Post.objects.filter(id=id, user_id=request.user_id).delete()
        if not deleted:
            return JsonResponse({'error': 'Not found'}, status=404)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@require_auth
def like_post(request, id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    existing = PostLike.objects.filter(post_id=id, user_id=request.user_id).first()
    if existing:
        existing.delete()
        liked = False
    else:
        PostLike.objects.create(post_id=id, user_id=request.user_id)
        liked = True
    count = PostLike.objects.filter(post_id=id).count()
    return JsonResponse({'liked': liked, 'count': count})


@csrf_exempt
@require_auth
def comments(request, id):
    if request.method == 'GET':
        result = Comment.objects.filter(post_id=id).select_related('user').order_by('created_at')
        return JsonResponse([{
            'id': c.id, 'post_id': c.post_id, 'user_id': c.user_id,
            'content': c.content, 'created_at': c.created_at.isoformat(),
            'username': c.user.username, 'avatar_color': c.user.avatar_color,
        } for c in result], safe=False)
    if request.method == 'POST':
        data = body(request)
        content = (data.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Content required'}, status=400)
        c = Comment.objects.create(post_id=id, user_id=request.user_id, content=content)
        c.refresh_from_db()
        user = User.objects.get(id=request.user_id)
        return JsonResponse({
            'id': c.id, 'post_id': c.post_id, 'user_id': c.user_id,
            'content': c.content, 'created_at': c.created_at.isoformat(),
            'username': user.username, 'avatar_color': user.avatar_color,
        })
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ── Dives ─────────────────────────────────────────────────────────────────────

def dive_dict(dive):
    return {
        'id': dive.id, 'user_id': dive.user_id, 'discipline': dive.discipline,
        'value': dive.value, 'notes': dive.notes,
        'dive_date': str(dive.dive_date), 'location': dive.location,
        'created_at': dive.created_at.isoformat(),
    }


@csrf_exempt
@require_auth
def dives(request):
    if request.method == 'POST':
        data = body(request)
        discipline = data.get('discipline')
        value = data.get('value')
        dive_date = data.get('dive_date')
        if not discipline or value is None or not dive_date:
            return JsonResponse({'error': 'Discipline, value, and date required'}, status=400)
        if discipline not in ('static', 'dynamic', 'depth'):
            return JsonResponse({'error': 'Invalid discipline'}, status=400)
        dive = Dive.objects.create(
            user_id=request.user_id, discipline=discipline,
            value=float(value), notes=data.get('notes') or '',
            dive_date=dive_date, location=data.get('location') or '',
        )
        return JsonResponse(dive_dict(dive))
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_auth
def user_dives(request, id):
    d = request.GET.get('discipline')
    qs = Dive.objects.filter(user_id=id)
    if d:
        qs = qs.filter(discipline=d)
    qs = qs.order_by('-dive_date', '-created_at')[:100]
    return JsonResponse([dive_dict(dv) for dv in qs], safe=False)


@csrf_exempt
@require_auth
def dive_detail(request, id):
    if request.method == 'DELETE':
        deleted, _ = Dive.objects.filter(id=id, user_id=request.user_id).delete()
        if not deleted:
            return JsonResponse({'error': 'Not found'}, status=404)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ── Buddies ───────────────────────────────────────────────────────────────────

@require_auth
def buddies(request):
    uid = request.user_id
    sql = """
        SELECT u.id, u.username, u.bio, u.location, u.avatar_color, br.created_at AS buddy_since
        FROM buddy_requests br
        JOIN users u ON (CASE WHEN br.sender_id=%s THEN br.receiver_id ELSE br.sender_id END) = u.id
        WHERE (br.sender_id=%s OR br.receiver_id=%s) AND br.status='accepted'
        ORDER BY u.username
    """
    with connection.cursor() as cur:
        cur.execute(sql, [uid, uid, uid])
        result = rows_as_dicts(cur)
    return JsonResponse(result, safe=False)


@require_auth
def buddy_requests_list(request):
    uid = request.user_id
    received = list(BuddyRequest.objects.filter(receiver_id=uid, status='pending')
                    .select_related('sender').order_by('-created_at').values(
                        'id', 'sender_id', 'created_at',
                        'sender__username', 'sender__bio', 'sender__avatar_color'))
    for r in received:
        r['username'] = r.pop('sender__username')
        r['bio'] = r.pop('sender__bio')
        r['avatar_color'] = r.pop('sender__avatar_color')
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None

    sent = list(BuddyRequest.objects.filter(sender_id=uid, status='pending')
                .select_related('receiver').order_by('-created_at').values(
                    'id', 'receiver_id', 'created_at',
                    'receiver__username', 'receiver__avatar_color'))
    for s in sent:
        s['username'] = s.pop('receiver__username')
        s['avatar_color'] = s.pop('receiver__avatar_color')
        s['created_at'] = s['created_at'].isoformat() if s['created_at'] else None

    return JsonResponse({'received': received, 'sent': sent})


@csrf_exempt
@require_auth
def buddy_request(request, id):
    if request.method == 'POST':
        uid = request.user_id
        tid = int(id)
        if tid == uid:
            return JsonResponse({'error': "Can't buddy yourself"}, status=400)
        existing = BuddyRequest.objects.filter(
            Q(sender_id=uid, receiver_id=tid) | Q(sender_id=tid, receiver_id=uid)
        ).first()
        if existing:
            return JsonResponse({'error': 'Request already exists'}, status=400)
        BuddyRequest.objects.create(sender_id=uid, receiver_id=tid)
        return JsonResponse({'success': True})

    if request.method == 'PUT':
        data = body(request)
        status = data.get('status')
        if status not in ('accepted', 'rejected'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        try:
            pending = BuddyRequest.objects.get(id=id, receiver_id=request.user_id, status='pending')
        except BuddyRequest.DoesNotExist:
            return JsonResponse({'error': 'Request not found'}, status=404)
        if status == 'rejected':
            pending.delete()
        else:
            pending.status = status
            pending.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@require_auth
def remove_buddy(request, id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    uid = request.user_id
    BuddyRequest.objects.filter(
        Q(sender_id=uid, receiver_id=id) | Q(sender_id=id, receiver_id=uid),
        status='accepted',
    ).delete()
    return JsonResponse({'success': True})


# ── Events ────────────────────────────────────────────────────────────────────

EVENTS_SELECT = """
    SELECT e.id, e.creator_id, e.title, e.description, e.location,
           e.event_date, e.discipline, e.max_participants, e.created_at,
           u.username AS creator_name, u.avatar_color AS creator_color,
           (SELECT COUNT(*) FROM event_participants WHERE event_id=e.id AND status='going')  AS going_count,
           (SELECT COUNT(*) FROM event_participants WHERE event_id=e.id AND status='maybe')  AS maybe_count,
           (SELECT status  FROM event_participants WHERE event_id=e.id AND user_id=%s)       AS user_status
    FROM events e JOIN users u ON e.creator_id=u.id
"""


@csrf_exempt
@require_auth
def events(request):
    if request.method == 'GET':
        sql = EVENTS_SELECT + "ORDER BY e.event_date ASC"
        with connection.cursor() as cur:
            cur.execute(sql, [request.user_id])
            result = rows_as_dicts(cur)
        return JsonResponse(result, safe=False)

    if request.method == 'POST':
        data = body(request)
        title = (data.get('title') or '').strip()
        event_date = data.get('event_date')
        if not title or not event_date:
            return JsonResponse({'error': 'Title and date required'}, status=400)
        ev = Event.objects.create(
            creator_id=request.user_id, title=title,
            description=data.get('description') or '',
            location=data.get('location') or '',
            event_date=event_date,
            discipline=data.get('discipline') or None,
            max_participants=data.get('max_participants') or None,
        )
        EventParticipant.objects.create(event_id=ev.id, user_id=request.user_id, status='going')
        sql = EVENTS_SELECT + "WHERE e.id=%s ORDER BY e.event_date ASC"
        with connection.cursor() as cur:
            cur.execute(sql, [request.user_id, ev.id])
            result = rows_as_dicts(cur)[0]
        return JsonResponse(result)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@require_auth
def event_participate(request, id):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    data = body(request)
    status = data.get('status')
    uid = request.user_id
    if status == 'not_going':
        EventParticipant.objects.filter(event_id=id, user_id=uid).delete()
    elif status in ('going', 'maybe'):
        ep, created = EventParticipant.objects.get_or_create(
            event_id=id, user_id=uid, defaults={'status': status}
        )
        if not created:
            ep.status = status
            ep.save()
    else:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    sql = EVENTS_SELECT + "WHERE e.id=%s ORDER BY e.event_date ASC"
    with connection.cursor() as cur:
        cur.execute(sql, [uid, id])
        result = rows_as_dicts(cur)[0]
    return JsonResponse(result)


@csrf_exempt
@require_auth
def event_detail(request, id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    deleted, _ = Event.objects.filter(id=id, creator_id=request.user_id).delete()
    if not deleted:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'success': True})

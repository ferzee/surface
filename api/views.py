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
                     Message, Notification, Post, PostLike, User)

COLORS = ['#0891b2', '#0e7490', '#1d4ed8', '#7c3aed', '#059669', '#b45309', '#be185d']
CERT_OPTIONS = {
    'AIDA 2', 'AIDA 3', 'AIDA 4', 'AIDA Instructor',
    'SSI Level 1', 'SSI Level 2', 'SSI Level 3', 'SSI Instructor',
    'PADI Freediver', 'PADI Advanced Freediver', 'PADI Master Freediver', 'PADI Instructor',
    'Molchanovs Wave 1', 'Molchanovs Wave 2', 'Molchanovs Wave 3',
}
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


HEADER_COLOR_KEYS = {'ocean', 'teal', 'midnight', 'slate', 'seafoam', 'dusk'}


def user_dict(user):
    try:
        certs = json.loads(user.certifications) if user.certifications else []
    except (ValueError, TypeError):
        certs = []
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'bio': user.bio,
        'location': user.location,
        'avatar_color': user.avatar_color,
        'avatar': user.avatar,
        'header_color': user.header_color,
        'certifications': certs,
        'diving_since': user.diving_since,
        'dive_school': user.dive_school,
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
        update_fields = {
            'bio': data.get('bio') or '',
            'location': data.get('location') or '',
            'dive_school': data.get('dive_school') or '',
        }
        new_username = (data.get('username') or '').strip()
        if new_username:
            if User.objects.filter(username=new_username).exclude(id=request.user_id).exists():
                return JsonResponse({'error': 'Username already taken'}, status=400)
            update_fields['username'] = new_username
        hc = data.get('header_color')
        if hc and hc in HEADER_COLOR_KEYS:
            update_fields['header_color'] = hc
        certs = data.get('certifications')
        if isinstance(certs, list):
            update_fields['certifications'] = json.dumps([c for c in certs if c in CERT_OPTIONS])
        ds = data.get('diving_since')
        if ds is not None:
            try:
                year = int(ds)
                update_fields['diving_since'] = year if 1950 <= year <= 2100 else None
            except (ValueError, TypeError):
                update_fields['diving_since'] = None
        elif 'diving_since' in data:
            update_fields['diving_since'] = None
        User.objects.filter(id=request.user_id).update(**update_fields)
        user = User.objects.get(id=request.user_id)
        return JsonResponse(user_dict(user))
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@require_auth
def upload_avatar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    file = request.FILES.get('avatar')
    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File too large (max 5 MB)'}, status=400)
    ct = (file.content_type or '').split(';')[0].strip()
    ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/gif': 'gif', 'image/webp': 'webp'}.get(ct)
    if not ext:
        return JsonResponse({'error': 'File must be a JPEG, PNG, GIF, or WebP image'}, status=400)
    avatars_dir = PUBLIC_DIR / 'avatars'
    avatars_dir.mkdir(exist_ok=True)
    for old in avatars_dir.glob(f"{request.user_id}.*"):
        old.unlink(missing_ok=True)
    dest = avatars_dir / f"{request.user_id}.{ext}"
    with open(dest, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    avatar_url = f"/avatars/{request.user_id}.{ext}"
    User.objects.filter(id=request.user_id).update(avatar=avatar_url)
    user = User.objects.get(id=request.user_id)
    return JsonResponse(user_dict(user))


@require_auth
def search_users(request):
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse([], safe=False)
    users = User.objects.filter(username__icontains=q).exclude(id=request.user_id)[:10]
    return JsonResponse([{
        'id': u.id, 'username': u.username, 'bio': u.bio,
        'location': u.location, 'avatar_color': u.avatar_color, 'avatar': u.avatar,
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
           u.username, u.avatar_color, u.avatar,
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
        try:
            post = Post.objects.get(id=id)
            if post.user_id != request.user_id:
                Notification.objects.update_or_create(
                    recipient_id=post.user_id, actor_id=request.user_id,
                    type='like', post_id=id,
                    defaults={'read': False},
                )
        except Post.DoesNotExist:
            pass
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
            'avatar': c.user.avatar,
        } for c in result], safe=False)
    if request.method == 'POST':
        data = body(request)
        content = (data.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Content required'}, status=400)
        c = Comment.objects.create(post_id=id, user_id=request.user_id, content=content)
        c.refresh_from_db()
        try:
            post = Post.objects.get(id=id)
            if post.user_id != request.user_id:
                Notification.objects.create(
                    recipient_id=post.user_id, actor_id=request.user_id,
                    type='comment', post_id=id,
                )
        except Post.DoesNotExist:
            pass
        user = User.objects.get(id=request.user_id)
        return JsonResponse({
            'id': c.id, 'post_id': c.post_id, 'user_id': c.user_id,
            'content': c.content, 'created_at': c.created_at.isoformat(),
            'username': user.username, 'avatar_color': user.avatar_color,
            'avatar': user.avatar,
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
        SELECT u.id, u.username, u.bio, u.location, u.avatar_color, u.avatar, br.created_at AS buddy_since
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
                        'sender__username', 'sender__bio', 'sender__avatar_color', 'sender__avatar'))
    for r in received:
        r['username'] = r.pop('sender__username')
        r['bio'] = r.pop('sender__bio')
        r['avatar_color'] = r.pop('sender__avatar_color')
        r['avatar'] = r.pop('sender__avatar')
        r['created_at'] = r['created_at'].isoformat() if r['created_at'] else None

    sent = list(BuddyRequest.objects.filter(sender_id=uid, status='pending')
                .select_related('receiver').order_by('-created_at').values(
                    'id', 'receiver_id', 'created_at',
                    'receiver__username', 'receiver__avatar_color', 'receiver__avatar'))
    for s in sent:
        s['username'] = s.pop('receiver__username')
        s['avatar_color'] = s.pop('receiver__avatar_color')
        s['avatar'] = s.pop('receiver__avatar')
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
        br = BuddyRequest.objects.create(sender_id=uid, receiver_id=tid)
        Notification.objects.create(
            recipient_id=tid, actor_id=uid, type='buddy_request', buddy_request=br,
        )
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
            Notification.objects.create(
                recipient_id=pending.sender_id, actor_id=request.user_id,
                type='buddy_accepted', buddy_request=pending,
            )
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
           u.username AS creator_name, u.avatar_color AS creator_color, u.avatar AS creator_avatar,
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


# ── Inbox / Messages ──────────────────────────────────────────────────────────

@require_auth
def inbox(request):
    uid = request.user_id

    notifs = list(
        Notification.objects.filter(recipient_id=uid)
        .select_related('actor', 'post')
        .order_by('-created_at')[:100]
    )
    notif_items = []
    for n in notifs:
        item = {
            'kind': 'notification',
            'id': n.id,
            'type': n.type,
            'read': n.read,
            'created_at': n.created_at.isoformat(),
            'actor_id': n.actor_id,
            'actor_username': n.actor.username,
            'actor_avatar_color': n.actor.avatar_color,
            'actor_avatar': n.actor.avatar,
        }
        if n.post_id:
            item['post_id'] = n.post_id
            item['post_excerpt'] = (n.post.content[:80] + '…') if n.post and len(n.post.content) > 80 else (n.post.content if n.post else '')
        if n.buddy_request_id:
            item['buddy_request_id'] = n.buddy_request_id
        notif_items.append(item)

    # One row per conversation (latest message per partner), grouped in Python
    all_msgs = list(
        Message.objects.filter(Q(sender_id=uid) | Q(receiver_id=uid))
        .order_by('-created_at')
        .select_related('sender', 'receiver')[:500]
    )
    seen_partners = set()
    convo_items = []
    for m in all_msgs:
        pid = m.receiver_id if m.sender_id == uid else m.sender_id
        if pid in seen_partners:
            continue
        seen_partners.add(pid)
        partner = m.receiver if m.sender_id == uid else m.sender
        unread = Message.objects.filter(sender_id=pid, receiver_id=uid, read=False).count()
        convo_items.append({
            'kind': 'message',
            'id': m.id,
            'partner_id': pid,
            'partner_username': partner.username,
            'partner_avatar_color': partner.avatar_color,
            'partner_avatar': partner.avatar,
            'last_message': m.content,
            'sender_id': m.sender_id,
            'unread_count': unread,
            'created_at': m.created_at.isoformat(),
        })

    return JsonResponse({'notifications': notif_items, 'conversations': convo_items})


@require_auth
def inbox_unread(request):
    uid = request.user_id
    count = (
        Notification.objects.filter(recipient_id=uid, read=False).count() +
        Message.objects.filter(receiver_id=uid, read=False).count()
    )
    return JsonResponse({'count': count})


@csrf_exempt
@require_auth
def notification_read(request, id):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    Notification.objects.filter(id=id, recipient_id=request.user_id).update(read=True)
    return JsonResponse({'success': True})


@csrf_exempt
@require_auth
def inbox_mark_read(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    uid = request.user_id
    Notification.objects.filter(recipient_id=uid, read=False).update(read=True)
    Message.objects.filter(receiver_id=uid, read=False).update(read=True)
    return JsonResponse({'success': True})


@csrf_exempt
@require_auth
def conversation(request, user_id):
    uid = request.user_id

    if request.method == 'GET':
        msgs = list(
            Message.objects.filter(
                Q(sender_id=uid, receiver_id=user_id) | Q(sender_id=user_id, receiver_id=uid)
            ).order_by('created_at')[:200]
        )
        Message.objects.filter(sender_id=user_id, receiver_id=uid, read=False).update(read=True)
        return JsonResponse([{
            'id': m.id,
            'sender_id': m.sender_id,
            'receiver_id': m.receiver_id,
            'content': m.content,
            'read': m.read,
            'created_at': m.created_at.isoformat(),
        } for m in msgs], safe=False)

    if request.method == 'POST':
        data = body(request)
        content = (data.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Content required'}, status=400)
        if not User.objects.filter(id=user_id).exists():
            return JsonResponse({'error': 'User not found'}, status=404)
        msg = Message.objects.create(sender_id=uid, receiver_id=user_id, content=content)
        return JsonResponse({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id,
            'content': msg.content,
            'read': msg.read,
            'created_at': msg.created_at.isoformat(),
        })

    return JsonResponse({'error': 'Method not allowed'}, status=405)

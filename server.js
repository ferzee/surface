'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { DatabaseSync } = require('node:sqlite');

const PORT = 3000;
const SECRET = process.env.SECRET || 'surface-dev-key-2024';
const PUBLIC = path.join(__dirname, 'public');

// ─── Database ─────────────────────────────────────────────────────────────────

const db = new DatabaseSync(path.join(__dirname, 'surface.db'));
db.exec('PRAGMA journal_mode = WAL');
db.exec('PRAGMA foreign_keys = ON');
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    email    TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    bio      TEXT DEFAULT '',
    location TEXT DEFAULT '',
    avatar_color TEXT DEFAULT '#0891b2',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS buddy_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status      TEXT DEFAULT 'pending',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sender_id, receiver_id)
  );
  CREATE TABLE IF NOT EXISTS dives (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    discipline TEXT NOT NULL CHECK(discipline IN ('static','dynamic','depth')),
    value      REAL NOT NULL,
    notes      TEXT DEFAULT '',
    dive_date  DATE NOT NULL,
    location   TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS post_likes (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY(post_id, user_id)
  );
  CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            TEXT NOT NULL,
    description      TEXT DEFAULT '',
    location         TEXT DEFAULT '',
    event_date       DATETIME NOT NULL,
    discipline       TEXT,
    max_participants INTEGER,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS event_participants (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status   TEXT DEFAULT 'going',
    PRIMARY KEY(event_id, user_id)
  );
`);

// ─── Auth helpers ─────────────────────────────────────────────────────────────

const COLORS = ['#0891b2','#0e7490','#1d4ed8','#7c3aed','#059669','#b45309','#be185d'];

function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.pbkdf2Sync(pw, salt, 100000, 64, 'sha512').toString('hex');
  return `${salt}:${hash}`;
}

function checkPassword(pw, stored) {
  const [salt, hash] = stored.split(':');
  const h = crypto.pbkdf2Sync(pw, salt, 100000, 64, 'sha512').toString('hex');
  if (h.length !== hash.length) return false;
  return crypto.timingSafeEqual(Buffer.from(h), Buffer.from(hash));
}

function createToken(userId) {
  const payload = Buffer.from(JSON.stringify({ u: userId, e: Date.now() + 30*24*60*60*1000 })).toString('base64url');
  const sig = crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');
  return `${payload}.${sig}`;
}

function verifyToken(token) {
  if (!token) return null;
  const dot = token.lastIndexOf('.');
  if (dot < 0) return null;
  const payload = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');
  try {
    const eBuf = Buffer.from(expected, 'base64url');
    const sBuf = Buffer.from(sig, 'base64url');
    if (eBuf.length !== sBuf.length) return null;
    if (!crypto.timingSafeEqual(eBuf, sBuf)) return null;
  } catch { return null; }
  const data = JSON.parse(Buffer.from(payload, 'base64url').toString());
  if (data.e < Date.now()) return null;
  return data.u;
}

// ─── HTTP helpers ─────────────────────────────────────────────────────────────

function parseBody(req) {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', c => data += c);
    req.on('end', () => {
      try { resolve(data ? JSON.parse(data) : {}); }
      catch { resolve({}); }
    });
    req.on('error', () => resolve({}));
  });
}

function send(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}

function getTokenFromReq(req) {
  const auth = req.headers['authorization'] || '';
  return auth.startsWith('Bearer ') ? auth.slice(7) : null;
}

// ─── Router ───────────────────────────────────────────────────────────────────

const routes = [];
function on(method, pattern, handler) {
  routes.push({ method, segs: pattern.split('/').filter(Boolean), handler });
}

function matchRoute(method, pathname) {
  const parts = pathname.split('/').filter(Boolean);
  for (const r of routes) {
    if (r.method !== method || r.segs.length !== parts.length) continue;
    const params = {};
    let ok = true;
    for (let i = 0; i < r.segs.length; i++) {
      if (r.segs[i][0] === ':') params[r.segs[i].slice(1)] = parts[i];
      else if (r.segs[i] !== parts[i]) { ok = false; break; }
    }
    if (ok) return { handler: r.handler, params };
  }
  return null;
}

// ─── Route definitions ────────────────────────────────────────────────────────

// AUTH
on('POST', '/api/auth/register', async (_req, res, { body }) => {
  const { username, email, password } = body;
  if (!username || !email || !password) return send(res, 400, { error: 'All fields required' });
  if (password.length < 6) return send(res, 400, { error: 'Password must be at least 6 characters' });
  const color = COLORS[Math.floor(Math.random() * COLORS.length)];
  try {
    const r = db.prepare('INSERT INTO users (username,email,password_hash,avatar_color) VALUES (?,?,?,?)')
      .run(username.trim(), email.toLowerCase().trim(), hashPassword(password), color);
    const user = db.prepare('SELECT id,username,email,bio,location,avatar_color,created_at FROM users WHERE id=?').get(r.lastInsertRowid);
    send(res, 200, { token: createToken(user.id), user });
  } catch (e) {
    send(res, 400, { error: e.message.includes('UNIQUE') ? 'Username or email already taken' : 'Could not create account' });
  }
});

on('POST', '/api/auth/login', async (_req, res, { body }) => {
  const { email, password } = body;
  const user = db.prepare('SELECT * FROM users WHERE email=?').get((email || '').toLowerCase().trim());
  if (!user || !checkPassword(password || '', user.password_hash))
    return send(res, 401, { error: 'Invalid email or password' });
  const { password_hash, ...safe } = user;
  send(res, 200, { token: createToken(user.id), user: safe });
});

// USERS
on('GET', '/api/users/me', async (_req, res, { userId }) => {
  const user = db.prepare('SELECT id,username,email,bio,location,avatar_color,created_at FROM users WHERE id=?').get(userId);
  send(res, 200, user);
});

on('GET', '/api/users/search', async (_req, res, { userId, query }) => {
  const q = (query.get('q') || '').trim();
  if (!q) return send(res, 200, []);
  const users = db.prepare('SELECT id,username,bio,location,avatar_color FROM users WHERE username LIKE ? AND id!=? LIMIT 10').all(`%${q}%`, userId);
  send(res, 200, users);
});

on('GET', '/api/users/:id', async (_req, res, { userId, params }) => {
  const tid = parseInt(params.id);
  const user = db.prepare('SELECT id,username,email,bio,location,avatar_color,created_at FROM users WHERE id=?').get(tid);
  if (!user) return send(res, 404, { error: 'User not found' });
  const rel = db.prepare('SELECT id,status,sender_id FROM buddy_requests WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)').get(userId, tid, tid, userId);
  const records = {
    static:  db.prepare("SELECT MAX(value) v FROM dives WHERE user_id=? AND discipline='static'").get(tid)?.v ?? null,
    dynamic: db.prepare("SELECT MAX(value) v FROM dives WHERE user_id=? AND discipline='dynamic'").get(tid)?.v ?? null,
    depth:   db.prepare("SELECT MAX(value) v FROM dives WHERE user_id=? AND discipline='depth'").get(tid)?.v ?? null,
  };
  const buddyCount = db.prepare("SELECT COUNT(*) c FROM buddy_requests WHERE (sender_id=? OR receiver_id=?) AND status='accepted'").get(tid, tid).c;
  const diveCount = db.prepare('SELECT COUNT(*) c FROM dives WHERE user_id=?').get(tid).c;
  send(res, 200, { ...user, buddyRelation: rel || null, records, buddyCount, diveCount });
});

on('PUT', '/api/users/me', async (_req, res, { userId, body }) => {
  db.prepare('UPDATE users SET bio=?,location=? WHERE id=?').run(body.bio || '', body.location || '', userId);
  const user = db.prepare('SELECT id,username,email,bio,location,avatar_color,created_at FROM users WHERE id=?').get(userId);
  send(res, 200, user);
});

// POSTS
function getPostsByWhere(viewerId, where, ...args) {
  return db.prepare(`
    SELECT p.*,u.username,u.avatar_color,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) like_count,
      (SELECT COUNT(*) FROM comments   WHERE post_id=p.id) comment_count,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id AND user_id=${viewerId}) user_liked
    FROM posts p JOIN users u ON p.user_id=u.id
    ${where} ORDER BY p.created_at DESC
  `).all(...args);
}

on('GET', '/api/posts/feed', async (_req, res, { userId }) => {
  const posts = db.prepare(`
    SELECT p.*,u.username,u.avatar_color,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) like_count,
      (SELECT COUNT(*) FROM comments   WHERE post_id=p.id) comment_count,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id AND user_id=?) user_liked
    FROM posts p JOIN users u ON p.user_id=u.id
    WHERE p.user_id=? OR p.user_id IN (
      SELECT CASE WHEN sender_id=? THEN receiver_id ELSE sender_id END
      FROM buddy_requests
      WHERE (sender_id=? OR receiver_id=?) AND status='accepted'
    )
    ORDER BY p.created_at DESC LIMIT 100
  `).all(userId, userId, userId, userId, userId);
  send(res, 200, posts);
});

on('GET', '/api/posts/user/:id', async (_req, res, { userId, params }) => {
  const posts = db.prepare(`
    SELECT p.*,u.username,u.avatar_color,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) like_count,
      (SELECT COUNT(*) FROM comments   WHERE post_id=p.id) comment_count,
      (SELECT COUNT(*) FROM post_likes WHERE post_id=p.id AND user_id=?) user_liked
    FROM posts p JOIN users u ON p.user_id=u.id
    WHERE p.user_id=? ORDER BY p.created_at DESC
  `).all(userId, parseInt(params.id));
  send(res, 200, posts);
});

on('POST', '/api/posts', async (_req, res, { userId, body }) => {
  if (!body.content?.trim()) return send(res, 400, { error: 'Content required' });
  const r = db.prepare('INSERT INTO posts (user_id,content) VALUES (?,?)').run(userId, body.content.trim());
  const post = db.prepare(`
    SELECT p.*,u.username,u.avatar_color, 0 like_count, 0 comment_count, 0 user_liked
    FROM posts p JOIN users u ON p.user_id=u.id WHERE p.id=?
  `).get(r.lastInsertRowid);
  send(res, 200, post);
});

on('DELETE', '/api/posts/:id', async (_req, res, { userId, params }) => {
  const post = db.prepare('SELECT * FROM posts WHERE id=? AND user_id=?').get(params.id, userId);
  if (!post) return send(res, 404, { error: 'Not found' });
  db.prepare('DELETE FROM posts WHERE id=?').run(params.id);
  send(res, 200, { success: true });
});

on('POST', '/api/posts/:id/like', async (_req, res, { userId, params }) => {
  const pid = parseInt(params.id);
  const existing = db.prepare('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?').get(pid, userId);
  if (existing) db.prepare('DELETE FROM post_likes WHERE post_id=? AND user_id=?').run(pid, userId);
  else          db.prepare('INSERT INTO post_likes (post_id,user_id) VALUES (?,?)').run(pid, userId);
  const count = db.prepare('SELECT COUNT(*) c FROM post_likes WHERE post_id=?').get(pid).c;
  send(res, 200, { liked: !existing, count });
});

on('GET', '/api/posts/:id/comments', async (_req, res, { params }) => {
  const comments = db.prepare(`
    SELECT c.*,u.username,u.avatar_color FROM comments c
    JOIN users u ON c.user_id=u.id WHERE c.post_id=? ORDER BY c.created_at ASC
  `).all(params.id);
  send(res, 200, comments);
});

on('POST', '/api/posts/:id/comments', async (_req, res, { userId, params, body }) => {
  if (!body.content?.trim()) return send(res, 400, { error: 'Content required' });
  const r = db.prepare('INSERT INTO comments (post_id,user_id,content) VALUES (?,?,?)').run(parseInt(params.id), userId, body.content.trim());
  const c = db.prepare('SELECT c.*,u.username,u.avatar_color FROM comments c JOIN users u ON c.user_id=u.id WHERE c.id=?').get(r.lastInsertRowid);
  send(res, 200, c);
});

// DIVES
on('POST', '/api/dives', async (_req, res, { userId, body }) => {
  const { discipline, value, notes, dive_date, location } = body;
  if (!discipline || value == null || !dive_date) return send(res, 400, { error: 'Discipline, value, and date required' });
  if (!['static','dynamic','depth'].includes(discipline)) return send(res, 400, { error: 'Invalid discipline' });
  const r = db.prepare('INSERT INTO dives (user_id,discipline,value,notes,dive_date,location) VALUES (?,?,?,?,?,?)')
    .run(userId, discipline, parseFloat(value), notes || '', dive_date, location || '');
  send(res, 200, db.prepare('SELECT * FROM dives WHERE id=?').get(r.lastInsertRowid));
});

on('GET', '/api/dives/user/:id', async (_req, res, { params, query }) => {
  const d = query.get('discipline');
  const sql = d
    ? 'SELECT * FROM dives WHERE user_id=? AND discipline=? ORDER BY dive_date DESC,created_at DESC LIMIT 100'
    : 'SELECT * FROM dives WHERE user_id=? ORDER BY dive_date DESC,created_at DESC LIMIT 100';
  const dives = d ? db.prepare(sql).all(params.id, d) : db.prepare(sql).all(params.id);
  send(res, 200, dives);
});

on('DELETE', '/api/dives/:id', async (_req, res, { userId, params }) => {
  const dive = db.prepare('SELECT * FROM dives WHERE id=? AND user_id=?').get(params.id, userId);
  if (!dive) return send(res, 404, { error: 'Not found' });
  db.prepare('DELETE FROM dives WHERE id=?').run(params.id);
  send(res, 200, { success: true });
});

// BUDDIES
on('GET', '/api/buddies', async (_req, res, { userId }) => {
  const buddies = db.prepare(`
    SELECT u.id,u.username,u.bio,u.location,u.avatar_color,br.created_at buddy_since
    FROM buddy_requests br
    JOIN users u ON (CASE WHEN br.sender_id=? THEN br.receiver_id ELSE br.sender_id END)=u.id
    WHERE (br.sender_id=? OR br.receiver_id=?) AND br.status='accepted'
    ORDER BY u.username
  `).all(userId, userId, userId);
  send(res, 200, buddies);
});

on('GET', '/api/buddies/requests', async (_req, res, { userId }) => {
  const received = db.prepare(`
    SELECT br.id,br.sender_id,br.created_at,u.username,u.bio,u.avatar_color
    FROM buddy_requests br JOIN users u ON br.sender_id=u.id
    WHERE br.receiver_id=? AND br.status='pending' ORDER BY br.created_at DESC
  `).all(userId);
  const sent = db.prepare(`
    SELECT br.id,br.receiver_id,br.created_at,u.username,u.avatar_color
    FROM buddy_requests br JOIN users u ON br.receiver_id=u.id
    WHERE br.sender_id=? AND br.status='pending' ORDER BY br.created_at DESC
  `).all(userId);
  send(res, 200, { received, sent });
});

on('POST', '/api/buddies/request/:userId', async (_req, res, { userId, params }) => {
  const tid = parseInt(params.userId);
  if (tid === userId) return send(res, 400, { error: "Can't buddy yourself" });
  const existing = db.prepare('SELECT 1 FROM buddy_requests WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)').get(userId, tid, tid, userId);
  if (existing) return send(res, 400, { error: 'Request already exists' });
  db.prepare('INSERT INTO buddy_requests (sender_id,receiver_id) VALUES (?,?)').run(userId, tid);
  send(res, 200, { success: true });
});

on('PUT', '/api/buddies/request/:requestId', async (_req, res, { userId, params, body }) => {
  const { status } = body;
  if (!['accepted','rejected'].includes(status)) return send(res, 400, { error: 'Invalid status' });
  const pending = db.prepare("SELECT * FROM buddy_requests WHERE id=? AND receiver_id=? AND status='pending'").get(params.requestId, userId);
  if (!pending) return send(res, 404, { error: 'Request not found' });
  if (status === 'rejected') db.prepare('DELETE FROM buddy_requests WHERE id=?').run(pending.id);
  else                       db.prepare('UPDATE buddy_requests SET status=? WHERE id=?').run(status, pending.id);
  send(res, 200, { success: true });
});

on('DELETE', '/api/buddies/:userId', async (_req, res, { userId, params }) => {
  db.prepare("DELETE FROM buddy_requests WHERE ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) AND status='accepted'")
    .run(userId, params.userId, params.userId, userId);
  send(res, 200, { success: true });
});

// EVENTS
function getEvents(viewerId, where, ...args) {
  return db.prepare(`
    SELECT e.*,u.username creator_name,u.avatar_color creator_color,
      (SELECT COUNT(*) FROM event_participants WHERE event_id=e.id AND status='going')  going_count,
      (SELECT COUNT(*) FROM event_participants WHERE event_id=e.id AND status='maybe')  maybe_count,
      (SELECT status FROM event_participants WHERE event_id=e.id AND user_id=${viewerId}) user_status
    FROM events e JOIN users u ON e.creator_id=u.id
    ${where} ORDER BY e.event_date ASC
  `).all(...args);
}

on('GET', '/api/events', async (_req, res, { userId }) => {
  send(res, 200, getEvents(userId, ''));
});

on('POST', '/api/events', async (_req, res, { userId, body }) => {
  const { title, description, location, event_date, discipline, max_participants } = body;
  if (!title?.trim() || !event_date) return send(res, 400, { error: 'Title and date required' });
  const r = db.prepare('INSERT INTO events (creator_id,title,description,location,event_date,discipline,max_participants) VALUES (?,?,?,?,?,?,?)')
    .run(userId, title.trim(), description || '', location || '', event_date, discipline || null, max_participants || null);
  db.prepare('INSERT INTO event_participants (event_id,user_id,status) VALUES (?,?,?)').run(r.lastInsertRowid, userId, 'going');
  send(res, 200, getEvents(userId, 'WHERE e.id=?', r.lastInsertRowid)[0]);
});

on('PUT', '/api/events/:id/participate', async (_req, res, { userId, params, body }) => {
  const eid = parseInt(params.id);
  const { status } = body;
  if (status === 'not_going') {
    db.prepare('DELETE FROM event_participants WHERE event_id=? AND user_id=?').run(eid, userId);
  } else if (['going','maybe'].includes(status)) {
    const ex = db.prepare('SELECT 1 FROM event_participants WHERE event_id=? AND user_id=?').get(eid, userId);
    if (ex) db.prepare('UPDATE event_participants SET status=? WHERE event_id=? AND user_id=?').run(status, eid, userId);
    else    db.prepare('INSERT INTO event_participants (event_id,user_id,status) VALUES (?,?,?)').run(eid, userId, status);
  } else return send(res, 400, { error: 'Invalid status' });
  send(res, 200, getEvents(userId, 'WHERE e.id=?', eid)[0]);
});

on('DELETE', '/api/events/:id', async (_req, res, { userId, params }) => {
  const ev = db.prepare('SELECT * FROM events WHERE id=? AND creator_id=?').get(params.id, userId);
  if (!ev) return send(res, 404, { error: 'Not found' });
  db.prepare('DELETE FROM events WHERE id=?').run(params.id);
  send(res, 200, { success: true });
});

// ─── Static file server ───────────────────────────────────────────────────────

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css',
  '.js':   'application/javascript',
};

function serveFile(res, filepath) {
  try {
    const content = fs.readFileSync(filepath);
    const ext = path.extname(filepath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
    res.end(content);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/html' });
    res.end('<h1>404 Not Found</h1>');
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const { pathname } = url;

  if (pathname.startsWith('/api/')) {
    const body = ['POST','PUT','PATCH'].includes(req.method) ? await parseBody(req) : {};
    const m = matchRoute(req.method, pathname);
    if (!m) return send(res, 404, { error: 'Route not found' });

    let userId = null;
    if (!pathname.startsWith('/api/auth/')) {
      userId = verifyToken(getTokenFromReq(req));
      if (!userId) return send(res, 401, { error: 'Unauthorized' });
    }

    try {
      await m.handler(req, res, { body, userId, params: m.params, query: url.searchParams });
    } catch (e) {
      console.error(e);
      send(res, 500, { error: 'Server error' });
    }
    return;
  }

  const filePath = (pathname === '/' || pathname === '/index.html')
    ? path.join(PUBLIC, 'login.html')
    : path.join(PUBLIC, pathname);

  serveFile(res, filePath);
});

server.listen(PORT, () => {
  console.log(`\n🌊  Surface is running at http://localhost:${PORT}\n`);
});

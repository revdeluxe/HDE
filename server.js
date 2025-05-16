const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
require('dotenv').config();
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3001;
const DB_PATH = process.env.SQLITE_DB_PATH || path.join(__dirname, 'db', 'hde.sqlite3');
const http = require('http').createServer(app);
const io = require('socket.io')(http);

// --- Max concurrent users for socket.io ---
const MAX_CONCURRENT_USERS = 20; // Set your desired limit here

io.use((socket, next) => {
  if (io.engine.clientsCount > MAX_CONCURRENT_USERS) {
    return next(new Error('Server is at max user capacity. Please try again later.'));
  }
  next();
});

// Track logged-in users and their socket IDs
const userSocketMap = new Map(); // uid -> socket.id

io.on('connection', (socket) => {
  console.log('Client connected', socket.id);

  // On login, client should emit 'register-user' with their uid
  socket.on('register-user', (uid) => {
    userSocketMap.set(uid, socket.id);
    socket.uid = uid;
  });

  // On disconnect, remove from map
  socket.on('disconnect', () => {
    if (socket.uid) userSocketMap.delete(socket.uid);
  });

  // Call signaling: call-user event
  socket.on('call-user', (data) => {
    // data: { targetUid, ... }
    const targetSocketId = userSocketMap.get(data.targetUid);
    if (targetSocketId) {
      io.to(targetSocketId).emit('incoming-call', data);
    }
  });
});

// Initialize SQLite DB
if (!fs.existsSync(path.join(__dirname, 'db'))) {
  fs.mkdirSync(path.join(__dirname, 'db'));
}
const db = new sqlite3.Database(DB_PATH, (err) => {
  if (err) throw err;
  // Run all schema files in /db/schema
  const SCHEMA_DIR = path.join(__dirname, 'db', 'schema');
  if (fs.existsSync(SCHEMA_DIR)) {
    fs.readdirSync(SCHEMA_DIR).forEach(file => {
      if (file.endsWith('.sql')) {
        const schema = fs.readFileSync(path.join(SCHEMA_DIR, file), 'utf8');
        db.exec(schema, (err) => {
          if (err) throw err;
        });
      }
    });
  }
});

// Middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true })); // ? For HTML form data
app.use(express.json()); // For JSON (optional)
app.use(cookieParser());

app.post('/login', (req, res) => {
  const { username, passphrase } = req.body;
  const ip = req.ip || req.headers['x-forwarded-for'] || req.connection.remoteAddress;
  const userAgent = req.headers['user-agent'] || 'Unknown';

  let uid = null;
  let loginSuccess = false;

  if (!username || !passphrase) {
    return res.status(400).json({ success: false, message: 'Missing username or password' });
  }

  db.get('SELECT * FROM users WHERE username = ? AND status = ?', [username, 'active'], (err, user) => {
    if (err) {
      db.run(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES (?, ?, ?, datetime('now'), ?, ?)`,
        [null, username, false, ip, userAgent]
      );
      return res.status(500).json({ success: false, message: 'Server error' });
    }
    if (!user) {
      db.run(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES (?, ?, ?, datetime('now'), ?, ?)`,
        [null, username, false, ip, userAgent]
      );
      return res.status(401).json({ success: false, message: 'Invalid credentials or inactive account' });
    }
    uid = user.uid;
    require('bcrypt').compare(passphrase, user.passphrase, (err, match) => {
      if (err || !match) {
        db.run(
          `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
           VALUES (?, ?, ?, datetime('now'), ?, ?)`,
          [uid, username, false, ip, userAgent]
        );
        return res.status(401).json({ success: false, message: 'Invalid credentials' });
      }
      loginSuccess = true;
      db.run(
        `UPDATE users SET login_timestamp = datetime('now'), device_info = ? WHERE uid = ?`,
        [userAgent, uid]
      );
      db.run(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES (?, ?, ?, datetime('now'), ?, ?)`,
        [uid, username, true, ip, userAgent]
      );
      res.cookie('loggedIn', 'true', { httpOnly: true, sameSite: 'lax' });
      // Respond with JSON containing role and username for client-side panel switching
      res.json({ success: true, role: user.role, username: user.username });
    });
  });
});

app.post('/logout', (req, res) => {
  res.clearCookie('loggedIn').json({ success: true });
});

app.use(/^\/admin(?:\/.*)?$/, (req, res) => {
  res.sendFile(path.join(publicDir, 'admin.html'));
});

// --- API: Get all users (for user management UI) ---
app.get('/api/users', (req, res) => {
  db.all('SELECT uid as id, username, role, status FROM users', [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

// --- API: Add user (for user management UI) ---
app.post('/api/users', async (req, res) => {
  const { username, password, role = 'user', status = 'active' } = req.body;
  if (!username || !password) return res.status(400).json({ error: 'Missing username or password' });
  try {
    const hashed = await require('bcrypt').hash(password, 10);
    db.run(
      'INSERT INTO users (username, passphrase, role, status, login_timestamp, device_info) VALUES (?, ?, ?, ?, datetime("now"), "API")',
      [username, hashed, role, status],
      function (err) {
        if (err) {
          if (err.message.includes('UNIQUE constraint failed')) {
            return res.status(409).json({ error: 'Username already exists' });
          }
          return res.status(500).json({ error: err.message });
        }
        res.json({ id: this.lastID, username, role, status });
      }
    );
  } catch (err) {
    res.status(500).json({ error: 'Server error' });
  }
});

// --- API: Delete user (for user management UI) ---
app.delete('/api/users/:id', (req, res) => {
  db.run('DELETE FROM users WHERE uid = ?', [req.params.id], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ success: true });
  });
});

// Static assets
const publicDir = path.join(__dirname, 'public');
app.use(express.static(publicDir));

app.use((req, res, next) => {
  if (req.path.endsWith('.html') || path.extname(req.path)) {
    // Don't fallback for file-like routes
    return res.status(404).send('Not Found');
  }
  res.sendFile(path.join(publicDir, 'index.html'));
});

// Serve all .html files in /public directly (fixes Not Found for deep links)
app.get('/:file([\w\-]+\.html'), (req, res) => {
  const file = path.join(publicDir, req.params.file);
  if (fs.existsSync(file)) {
    res.sendFile(file);
  } else {
    res.status(404).send('Not Found');
  }
};

// Start server
app.listen(PORT, () => {
  console.log(`?? Server running at http://localhost:${PORT}`);
});

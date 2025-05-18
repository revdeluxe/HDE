// Declare dependencies

const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
require('dotenv').config();
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const http = require('http');
const https = require('https');
const bcrypt = require('bcrypt');
const { execFile } = require('child_process');
const app = express();

// Constants

const publicDir = path.join(__dirname, 'public');
const DB_PATH = process.env.SQLITE_DB_PATH || path.join(__dirname, 'db', 'hde.sqlite3');
const SSL_KEY = fs.readFileSync(path.join(__dirname, 'ssl', 'server.key'));
const SSL_CERT = fs.readFileSync(path.join(__dirname, 'ssl', 'server.cert'));
const HTTPS_PORT = process.env.HTTPS_PORT || 443;
const HTTP_PORT = process.env.HTTP_PORT || 80;

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
app.use(express.static(publicDir));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  next();
});

// Register endpoint
app.post('/register', (req, res) => {
  const { username, passphrase, role, status } = req.body;
  if (!username || !passphrase || !role || !status) {
    return res.status(400).json({ success: false, message: 'All fields required.' });
  }
  bcrypt.hash(passphrase, 10, (err, hash) => {
    if (err) return res.status(500).json({ success: false, message: 'Hashing error' });
    db.run(
      `INSERT INTO users (username, passphrase, role, status, login_timestamp, device_info)
       VALUES (?, ?, ?, ?, null, null)`,
      [username, hash, role, status],
      function (err) {
        if (err) {
          return res.status(500).json({ success: false, message: 'Insert error', error: err.message });
        }
        res.json({ success: true, uid: this.lastID });
      }
    );
  });
});

// Login endpoint
app.post('/login', (req, res) => {
  const { username, passphrase } = req.body;
  const ip = req.ip || req.headers['x-forwarded-for'] || req.connection.remoteAddress;
  const userAgent = req.headers['user-agent'] || 'Unknown';

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
    const uid = user.uid;
    bcrypt.compare(passphrase, user.passphrase, (err, match) => {
      if (err || !match) {
        db.run(
          `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
           VALUES (?, ?, ?, datetime('now'), ?, ?)`,
          [uid, username, false, ip, userAgent]
        );
        return res.status(401).json({ success: false, message: 'Invalid credentials' });
      }
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
      res.json({ success: true, role: user.role, username: user.username });
    });
  });
});

// Logout endpoint
app.post('/logout', (req, res) => {
  res.clearCookie('loggedIn').json({ success: true });
});

// Admin route (no regex)
app.get('/admin', (req, res) => {
  res.sendFile(path.join(publicDir, 'admin.html'));
});

// --- API: Get all users ---
app.get('/api/users', (req, res) => {
  db.all('SELECT uid as id, username, role, status FROM users', [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

// --- API: Add user ---
app.post('/api/users', async (req, res) => {
  const { username, password, role = 'user', status = 'active' } = req.body;
  if (!username || !password) return res.status(400).json({ error: 'Missing username or password' });
  try {
    const hashed = await bcrypt.hash(password, 10);
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

// --- API: Delete user ---
app.delete('/api/users/:id', (req, res) => {
  db.run('DELETE FROM users WHERE uid = ?', [req.params.id], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ success: true });
  });
});

// Serve all .html files in /public directly (fixes Not Found for deep links)
app.get('/:file', (req, res) => {
  if (!req.params.file.endsWith('.html')) return res.status(404).send('Not Found');
  const file = path.join(publicDir, req.params.file);
  if (fs.existsSync(file)) {
    res.sendFile(file);
  } else {
    res.status(404).send('Not Found');
  }
});

// Lo-Ra endpoint
app.get('/lora', (req, res) => {
  execFile('python3', ['serial/lora_read.py'], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ error: stderr || error.message });
    }
    try {
      const data = JSON.parse(stdout);
      res.json(data);
    } catch (e) {
      res.status(500).json({ error: 'Failed to parse output' });
    }
  });
});

// Lo-Ra send endpoint
app.post('/lora/send', (req, res) => {
  const { message } = req.body;
  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ success: false, error: 'Message required' });
  }
  // Call lora_send.py with the message as argument
  execFile('python3', ['serial/lora_send.py', message], (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ success: false, error: stderr || error.message });
    }
    res.json({ success: true, status: stdout.trim() });
  });
});

// Fallback for SPA
app.use((req, res, next) => {
  if (req.path.endsWith('.html') || path.extname(req.path)) {
    return res.status(404).send('Not Found');
  }
  res.sendFile(path.join(publicDir, 'index.html'));
});

// --- HTTPS Server ---
https.createServer({ key: SSL_KEY, cert: SSL_CERT }, app)
  .listen(HTTPS_PORT, () => {
    console.log(`HTTPS Server running on port ${HTTPS_PORT}`);
  });

// --- HTTP Server: Redirect to HTTPS ---
http.createServer((req, res) => {
  const host = req.headers['host'].replace(/:\d+$/, `:${HTTPS_PORT}`);
  res.writeHead(301, { Location: `https://${host}${req.url}` });
  res.end();
}).listen(HTTP_PORT, () => {
  console.log(`HTTP Server redirecting all traffic to HTTPS`);
});

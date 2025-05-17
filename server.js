const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
require('dotenv').config();
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const http = require('http');
const https = require('https');
const app = express();
const DB_PATH = process.env.SQLITE_DB_PATH || path.join(__dirname, 'db', 'hde.sqlite3');
const SSL_KEY = fs.readFileSync(path.join(__dirname, 'ssl', 'server.key'));
const SSL_CERT = fs.readFileSync(path.join(__dirname, 'ssl', 'server.cert'));
const PORT = process.env.PORT || 3001;
const HTTPS_PORT = process.env.HTTPS_PORT || 443;
const HTTP_PORT = process.env.HTTP_PORT || 80;
const { execFile } = require('child_process');
const port = 3000;



https.createServer({ key: SSL_KEY, cert: SSL_CERT }, app)
  .listen(HTTPS_PORT, () => {
    console.log(`?? HTTPS Server running on port ${HTTPS_PORT}`);
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

app.use(express.static('Public'));

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

app.listen(port, () => console.log(`Server running on http://localhost:${port}`));

// Middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true })); // ? For HTML form data
app.use(express.json()); // For JSON (optional)
app.use(cookieParser());

app.post('/register', async (req, res) => {
  const { username, passphrase, role } = req.body;
  if (!username || !passphrase || !role) {
    return res.status(400).json({ success: false, message: 'Missing required fields' });
  }
  try {
    const hashed = await require('bcrypt').hash(passphrase, 10);
    db.run(
      'INSERT INTO users (username, passphrase, role, status, login_timestamp, device_info) VALUES (?, ?, ?, ?, datetime("now"), "register")',
      [username, hashed, role, 'active'],
      function (err) {
        if (err) {
          if (err.message.includes('UNIQUE constraint failed')) {
            return res.status(409).json({ success: false, message: 'Username already exists' });
          }
          return res.status(500).json({ success: false, message: 'Server error' });
        }
        res.json({ success: true, id: this.lastID, username, role });
      }
    );
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error' });
  }
});

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


// --- HTTP Server: Redirect to HTTPS ---
http.createServer((req, res) => {
  const host = req.headers['host'].replace(/:\d+$/, `:${HTTPS_PORT}`);
  res.writeHead(301, { Location: `https://${host}${req.url}` });
  res.end();
}).listen(HTTP_PORT, () => {
  console.log(`?? HTTP Server redirecting all traffic to HTTPS`);
});

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
const { exec } = require('child_process');
const crypto = require('crypto');



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

// --- API: Search Asterisk Contacts (for phonebook.html and phonebook_user.html) ---
app.get('/api/asterisk/contacts', (req, res) => {
  const searchQuery = req.query.search || '';
  const sanitizedQuery = searchQuery.replace(/[^a-zA-Z0-9\s_-]/g, '').toLowerCase();

  exec('asterisk -rx "pjsip show contacts"', (error, stdout, stderr) => {
    if (error) {
      console.error('❌ Exec error:', error.message);
      return res.status(500).json({ error: error.message });
    }

    console.log('[stdout]', stdout);
    console.log('[stderr]', stderr);

    res.json({ rawOutput: stdout });

    const contacts = [];
    const lines = stdout.split('\n');
    lines.forEach(line => {
      const match = line.match(/^(.*?)\s+(.*?)\s+(.*?)\s+Avail\s+(.*?)\s+/);
      if (match) {
        const name = match[1].trim();
        const contact = match[2].trim();
        const availability = match[4].trim();
        if (
          name.toLowerCase().includes(sanitizedQuery) ||
          contact.toLowerCase().includes(sanitizedQuery)
        ) {
          contacts.push({ name, contact, availability });
        }
      }
    });

    res.json(contacts);
  });
});

app.post('/register', async (req, res) => {
  let { username, passphrase, role, status } = req.body;

  if (!username || !passphrase || !role || !status) {
    return res.status(400).send('All fields are required');
  }

  // Sanitize inputs
  username = username.replace(/[^a-zA-Z0-9_-]/g, '');
  passphrase = passphrase.replace(/[^a-zA-Z0-9!@#$%^&*()_+=-]/g, '');

  // Check if username already exists
  db.get('SELECT * FROM users WHERE username = ?', [username], async (err, row) => {
    if (err) return res.status(500).send('Database error');

    if (row) {
      return res.status(409).send('❗ Username already exists. Please choose another one.');
    }

    const hashedPassphrase = await bcrypt.hash(passphrase, 10);
    const loginTimestamp = new Date().toISOString();
    const deviceInfo = JSON.stringify({
      user_agent: req.headers['user-agent'],
      ip_address: req.headers['x-forwarded-for'] || req.connection.remoteAddress,
    });

    const insertQuery = `
      INSERT INTO users (username, passphrase, role, status, login_timestamp, device_info)
      VALUES (?, ?, ?, ?, ?, ?)
    `;

    db.run(insertQuery, [username, hashedPassphrase, role, status, loginTimestamp, deviceInfo], function (err) {
      if (err) {
        console.error('❌ Database error during registration:', err.message);
        return res.status(500).send("Failed to register user.");
      }

      res.send(`<h3>✅ Registration successful!</h3><p>User <strong>${username}</strong> has been added to the system.</p><a href="/register.html">Go back</a>`);
    });
  });
});


app.post('/login', (req, res) => {
  const { username, passphrase } = req.body;
  const ip = req.ip || req.headers['x-forwarded-for'] || req.socket.remoteAddress;
  const userAgent = req.headers['user-agent'] || 'Unknown';

  if (!username || !passphrase) {
    return res.status(400).json({ success: false, message: 'Missing username or password' });
  }

  db.get('SELECT * FROM users WHERE LOWER(username) = ?', [username.toLowerCase()], (err, user) => {
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
      return res.status(401).json({ success: false, message: 'Invalid credentials or account does not exist' });
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
        `UPDATE users SET login_timestamp = datetime('now'), device_info = ?, status = 'online' WHERE uid = ?`,
        [userAgent, uid]
      );
      db.run(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES (?, ?, ?, datetime('now'), ?, ?)`,
        [uid, username, true, ip, userAgent]
      );

      // Fetch user info and set cookie
      res.cookie('loggedIn', 'true', { httpOnly: true, sameSite: 'lax' });
      res.cookie('username', username, { httpOnly: true, sameSite: 'lax' });

      // Redirect to the appropriate dashboard based on role
      const dashboard = user.role === 'admin' ? 'admin.html' : 'user.html';
      res.json({ 
        success: true, 
        message: 'Login successful', 
        role: user.role, // Include role in the response
        dashboard: dashboard // Include dashboard in the response
      });
    });
  });
});

async function isOnline(username) {
  return new Promise((resolve, reject) => {
    db.get('SELECT status FROM users WHERE username = ?', [username], (err, row) => {
      if (err) return reject(err);
      resolve(row && row.status === 'online');
    });
  });
}

// Logout endpoint
app.post('/logout', (req, res) => {
  res.clearCookie('loggedIn').json({ success: true });
});

// Admin route (no regex)
app.get('/admin', (req, res) => {
  const username = req.cookies.username;
  if (!username) {
    return res.status(401).send('Unauthorized: No username provided');
  }
  if (username !== 'admin') {
    return res.status(403).send('Forbidden: Access restricted to admin users only');
  }
  isOnline(username)
    .then((online) => {
      if (!online) {
        return res.status(403).send('Forbidden: User is not online');
      }
      res.sendFile(path.join(publicDir, 'admin.html'), { headers: { 'Content-Security-Policy': `script-src 'self';` } }, (err) => {
        if (err) {
          console.error('Error sending admin.html:', err);
          res.status(500).send('Internal Server Error');
        }
      });
    })
    .catch((err) => {
      console.error('Error checking online status:', err);
      res.status(500).send('Internal Server Error');
    });
});

app.get('/api/greeting', (req, res) => {
  const username = req.cookies.username;
  if (!username) {
    return res.status(401).json({ greeting: null });
  }
  res.json({ greeting: `Welcome, ${username}!` });
});

app.get('/api/check-session', (req, res) => {
  const loggedIn = req.cookies.loggedIn === 'true';
  const username = req.cookies.username;

  if (!loggedIn || !username) {
    return res.status(401).json({ loggedIn: false });
  }

  isOnline(username)
    .then((online) => {
      if (!online) {
        return res.status(401).json({ loggedIn: false });
      }
      res.json({ loggedIn: true });
    })
    .catch((err) => {
      console.error('Error checking online status:', err);
      res.status(500).json({ loggedIn: false });
    });
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
      [username.toLowerCase(), hashed, role, status],
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

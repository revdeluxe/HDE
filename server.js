const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
require('dotenv').config();
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3001;

const pool = new Pool({
  user: process.env.PG_USER,       // e.g. 'postgres'
  host: process.env.PG_HOST,       // e.g. 'localhost'
  database: process.env.PG_DB,     // e.g. 'mydb'
  password: process.env.PG_PASS,   // your DB password
  port: process.env.PG_PORT || 5432,
});

// Middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true })); // ? For HTML form data
app.use(express.json()); // For JSON (optional)
app.use(cookieParser());

app.post('/login', async (req, res) => {
  const { username, passphrase } = req.body;
  const ip = req.ip || req.headers['x-forwarded-for'] || req.connection.remoteAddress;
  const userAgent = req.headers['user-agent'] || 'Unknown';

  console.log(`[${new Date().toISOString()}] Login attempt: username="${username}", IP=${ip}, UserAgent="${userAgent}"`);

  let uid = null;     // will assign if user exists
  let loginSuccess = false;

  try {
    if (!username || !passphrase) {
      console.warn(`[${new Date().toISOString()}] Missing username or password`);
      return res.status(400).json({ success: false, message: 'Missing username or password' });
    }

    console.log(`[${new Date().toISOString()}] Querying user table for username="${username}" and active status`);
    const userQuery = 'SELECT * FROM users WHERE username = $1 AND status = $2';
    const userResult = await pool.query(userQuery, [username, 'active']);
    console.log(`[${new Date().toISOString()}] User query result count: ${userResult.rows.length}`);

    if (userResult.rows.length === 0) {
      console.warn(`[${new Date().toISOString()}] No active user found with username="${username}"`);
      // Log attempt - no user found
      await pool.query(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES ($1, $2, $3, NOW(), $4, $5)`,
        [null, username, false, ip, userAgent]
      );
      return res.status(401).json({ success: false, message: 'Invalid credentials or inactive account' });
    }

    const user = userResult.rows[0];
    uid = user.uid;

    console.log(`[${new Date().toISOString()}] Comparing passphrase for uid=${uid}`);
    const match = await bcrypt.compare(passphrase, user.passphrase);

    if (!match) {
      console.warn(`[${new Date().toISOString()}] Password mismatch for uid=${uid}`);
      // Log failed attempt for known user
      await pool.query(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES ($1, $2, $3, NOW(), $4, $5)`,
        [uid, username, false, ip, userAgent]
      );
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }

    loginSuccess = true;
    console.log(`[${new Date().toISOString()}] Login successful for uid=${uid}`);

    // Update login_timestamp and device_info
    const updateQuery = `
      UPDATE users SET login_timestamp = NOW(), device_info = $1 WHERE uid = $2
    `;
    await pool.query(updateQuery, [userAgent, uid]);
    console.log(`[${new Date().toISOString()}] Updated login timestamp and device info for uid=${uid}`);

    // Log successful login
    await pool.query(
      `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
       VALUES ($1, $2, $3, NOW(), $4, $5)`,
      [uid, username, true, ip, userAgent]
    );
    console.log(`[${new Date().toISOString()}] Logged successful login attempt for uid=${uid}`);

    // Set cookie and respond success
    res.cookie('loggedIn', 'true', { httpOnly: true, sameSite: 'lax' });
    res.json({ success: true, role: user.role, username: user.username });

  } catch (error) {
    console.error(`[${new Date().toISOString()}] Login error:`, error);

    // Log failed attempt on server error
    try {
      await pool.query(
        `INSERT INTO login_attempts (uid, username, success, attempt_timestamp, ip_address, user_agent)
         VALUES ($1, $2, $3, NOW(), $4, $5)`,
        [uid, username || null, false, ip, userAgent]
      );
      console.log(`[${new Date().toISOString()}] Logged failed login attempt due to error`);
    } catch (logErr) {
      console.error(`[${new Date().toISOString()}] Failed to log login attempt:`, logErr);
    }

    res.status(500).json({ success: false, message: 'Server error' });
  }
});

app.post('/logout', (req, res) => {
  res.clearCookie('loggedIn').json({ success: true });
});

// Static assets
const publicDir = path.join(__dirname, 'public');
app.use(express.static(publicDir));

// ? Safe fallback for unmatched routes
app.use((req, res) => {
  res.sendFile(path.join(publicDir, 'index.html'));
});

// Start server
app.listen(PORT, () => {
  console.log(`?? Server running at http://localhost:${PORT}`);
});

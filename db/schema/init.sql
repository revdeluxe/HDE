-- SQLite schema for users table
CREATE TABLE IF NOT EXISTS users (
  uid INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  passphrase TEXT NOT NULL,
  role TEXT,
  status TEXT,
  login_timestamp DATETIME,
  device_info TEXT
);

-- SQLite schema for login_attempts table
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid INTEGER,
  username TEXT,
  success BOOLEAN,
  attempt_timestamp DATETIME,
  ip_address TEXT,
  user_agent TEXT
);

CREATE TABLE lora_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL
);
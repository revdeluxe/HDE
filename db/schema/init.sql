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


CREATE TABLE IF NOT EXISTS lora_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ps_contacts (
    id VARCHAR(255) PRIMARY KEY,
    uri VARCHAR(255),
    expiration_time INTEGER,
    qualify_frequency INTEGER,
    outbound_proxy VARCHAR(40),
    path VARCHAR(255),
    user_agent VARCHAR(255),
    reg_server VARCHAR(40),
    authenticate_qualify VARCHAR(5),
    via_addr VARCHAR(40),
    via_port INTEGER,
    call_id VARCHAR(255),
    prune_on_boot VARCHAR(5),
    endpoint VARCHAR(40)
);

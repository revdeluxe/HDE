// static/app.js

// ——————————————————————————————————
// Constants & State

const POLL_INTERVAL_MS = 3000;
const CHUNK_POLL_INTERVAL = POLL_INTERVAL_MS;
const seenMessages = new Set();
let unreadCount = 0;
let sendBtn;
let user = null;

// ——————————————————————————————————
// Utility Functions

function getCookie(name) {
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + name + '=([^;]*)')
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function scrollToBottom() {
  const container = document.getElementById('messages');
  container.scrollTop = container.scrollHeight;
}

function updateHttpStatus(res) {
  const el = document.getElementById('httpStatus');
  if (!el) return;

  el.className = 'status status-code';
  const code = res.status;
  el.textContent = `${code} ${res.statusText || ''}`;

  if (code >= 200 && code < 300) {
    el.classList.add('success');
  } else if (code >= 300 && code < 400) {
    el.classList.add('redirect');
  } else if (code >= 400 && code < 500) {
    el.classList.add('client-error');
  } else if (code >= 500) {
    el.classList.add('server-error');
  }
}

function appendMessage({ from, message, status = 'received', key }) {
  if (key && seenMessages.has(key)) return;
  if (key) seenMessages.add(key);

  const wrapper = document.createElement('div');
  wrapper.className = `message ${status}`;
  wrapper.innerHTML = `
    <strong>${from}:</strong> ${message}
    <span class="status-icon"></span>
  `;

  document.getElementById('messages').appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function showNotification() {
  const bubble = document.getElementById('notificationBubble');
  if (!bubble) return;

  unreadCount += 1;
  bubble.textContent = unreadCount > 1 ? unreadCount : '';
  bubble.classList.remove('hidden');
  bubble.classList.add('visible');

  setTimeout(() => {
    bubble.classList.remove('visible');
    bubble.classList.add('hidden');
  }, 3000);
}

// ——————————————————————————————————
// Core Logic

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const input = document.getElementById('messageInput');
  const form  = document.getElementById('messageForm');
  sendBtn      = form.querySelector('button');

  // Identify user
  user = getCookie('username');
  if (!user) {
    user = prompt('Enter your username:') || 'Anonymous';
    document.cookie = `username=${user}; path=/`;
  }
  document.getElementById('usernameField').textContent = user;

  // Send form handler
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';

    const timestamp = Date.now();
    const key       = `${user}|${text}|${timestamp}`;

    // Show pending message
    const msgEl = appendMessage({
      from: user,
      message: text,
      status: 'pending',
      key
    });

    try {
      // 1) Queue on server
      const res = await fetch('/api/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: user, message: text, timestamp })
      });
      updateHttpStatus(res);
      if (!res.ok) throw new Error(res.status);

      msgEl.classList.replace('pending', 'sent');

      // 2) Trigger sync loop
      const syncRes = await fetch('/api/sync', { method: 'POST' });
      updateHttpStatus(syncRes);
      if (syncRes.ok) {
        msgEl.classList.replace('sent', 'synced');
      }
    } catch {
      msgEl.classList.replace('pending', 'error');
    }
  });

  // Clear unread count on focus
  input.addEventListener('focus', () => {
    unreadCount = 0;
    const bubble = document.getElementById('notificationBubble');
    if (bubble) {
      bubble.classList.remove('visible');
      bubble.classList.add('hidden');
    }
  });

  // Initial load
  refreshStatus();
  pollReceive();

  // Poll periodically
  setInterval(() => {
    refreshStatus();
    pollReceive();
  }, POLL_INTERVAL_MS);
});

// ——————————————————————————————————
// Polling & Status

async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    updateHttpStatus(res);

    if (!res.ok) {
      sendBtn.disabled = true;
      sendBtn.textContent = 'Send';
      return;
    }

    const {
      rx_mode,
      tx_queue_depth,
      rssi,
      snr,
      busy,
      server_state
    } = await res.json();

    document.getElementById('rxMode').textContent      = rx_mode ? 'ON' : 'OFF';
    document.getElementById('queueDepth').textContent  = tx_queue_depth;
    document.getElementById('rssi').textContent        = rssi ?? '—';
    document.getElementById('snr').textContent         = snr  ?? '—';
    document.getElementById('serverState').textContent = server_state;

    const isSyncing = tx_queue_depth > 0 || busy;
    sendBtn.disabled = isSyncing;
    sendBtn.textContent = isSyncing ? 'Syncing…' : 'Send';
  } catch (err) {
    console.error('Status refresh failed', err);
    sendBtn.disabled = true;
    sendBtn.textContent = 'Send';
  }
}

async function pollReceive() {
  try {
    const res = await fetch('/api/receive');
    if (!res.ok) return;

    const { message, quality, meta } = await res.json();
    const key = `${message.from}|${message.message}|${message.timestamp || ''}`;
    const isMine = message.from === user;

    appendMessage({
      from: message.from,
      message: message.message,
      status: isMine ? 'synced' : 'received',
      key
    });

    if (!isMine) showNotification();
  } catch (err) {
    console.warn('Receive poll failed', err);
  }
}

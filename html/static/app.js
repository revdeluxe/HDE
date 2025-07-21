// static/app.js

// Keep track of seen messages
const seenMessages = new Set();
let sendBtn;

// Current user (top-level scope)
let user = null;

// ——————————————————————————————————
// Helper Functions

function getCookie(name) {
  const m = document.cookie.match(
    new RegExp('(?:^|; )' + name + '=([^;]*)')
  );
  return m ? decodeURIComponent(m[1]) : null;
}

function scrollToBottom() {
  const c = document.getElementById('messages');
  c.scrollTop = c.scrollHeight;
}

function updateHttpStatus(res) {
  const el = document.getElementById('httpStatus');
  if (!el) return;
  el.className = 'status status-code';
  const code = res.status;
  const text = res.statusText || '';
  if (code >= 200 && code < 300) {
    el.classList.add('success');
  } else if (code >= 300 && code < 400) {
    el.classList.add('redirect');
  } else if (code >= 400 && code < 500) {
    el.classList.add('client-error');
  } else if (code >= 500) {
    el.classList.add('server-error');
  }
  el.textContent = `${code} ${text}`;
}

function appendMessage({ from, message, status = 'received', key }) {
  if (key && seenMessages.has(key)) return;
  if (key) seenMessages.add(key);

  const div = document.createElement('div');
  div.className = `message ${status}`;
  div.innerHTML = `
    <strong>${from}:</strong> ${message}
    <span class="status-icon"></span>
  `;
  document.getElementById('messages').append(div);
  scrollToBottom();
  return div;
}

// Notification bubble
let unreadCount = 0;
function showNotification() {
  const b = document.getElementById('notificationBubble');
  if (!b) return;
  unreadCount++;
  b.textContent = unreadCount > 1 ? unreadCount : '';
  b.classList.remove('hidden');
  b.classList.add('visible');
  setTimeout(() => {
    b.classList.remove('visible');
    b.classList.add('hidden');
  }, 3000);
}

// ——————————————————————————————————
// Core Logic

document.addEventListener('DOMContentLoaded', () => {
  // Grab input and form
  const input = document.getElementById('messageInput');
  const form = document.getElementById('messageForm');
  sendBtn = form.querySelector('button');

  // Initialize user
  user = getCookie('username');
  if (!user) {
    user = prompt('Enter your username:') || 'Anonymous';
    document.cookie = `username=${user}; path=/`;
  }
  document.getElementById('usernameField').textContent = user;

  // Submit handler
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';

    // Unique key for this message
    const ts = Date.now();
    const myKey = `${user}|${text}|${ts}`;

    const msgEl = appendMessage({
      from: user,
      message: text,
      status: 'pending',
      key: myKey
    });

    try {
      const res = await fetch('/api/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: user, message: text, timestamp: ts })
      });
      updateHttpStatus(res);
      if (!res.ok) throw new Error(res.status);

      msgEl.classList.replace('pending', 'sent');

      const syncRes = await fetch('/api/sync', { method: 'POST' });
      updateHttpStatus(syncRes);
      if (syncRes.ok) {
        msgEl.classList.replace('sent', 'synced');
      }
    } catch {
      msgEl.classList.replace('pending', 'error');
    }
  });

  // Clear notifications when focusing input
  input.addEventListener('focus', () => {
    unreadCount = 0;
    const b = document.getElementById('notificationBubble');
    if (b) {
      b.classList.remove('visible');
      b.classList.add('hidden');
    }
  });

  // Initial load & polling
  refreshStatus();
  pollReceive();

  setInterval(() => {
    refreshStatus();
    pollReceive();
  }, 3000);
});

// ——————————————————————————————————
// Polling Functions

async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    updateHttpStatus(res);
    const {
      rx_mode,
      tx_queue_depth,
      server_state,
      busy,
      sync_status // optional if you want to expose sync info from backend
    } = await res.json();

    // Update RX/TX indicators
    document.getElementById('rxMode').textContent = rx_mode ? 'ON' : 'OFF';
    document.getElementById('queueDepth').textContent = tx_queue_depth;
    document.getElementById('healthStatus').textContent = res.ok ? 'OK' : 'Error';
    document.getElementById('serverState').textContent = server_state;

    // Update Send button
    const isSyncing = tx_queue_depth > 0 || busy;
    sendBtn.disabled = isSyncing;
    sendBtn.textContent = isSyncing ? `Syncing...` : 'Send';

    // Optionally display sync status
    const syncEl = document.getElementById('syncStatus');
    if (syncEl && sync_status) {
      syncEl.textContent = sync_status;
    }

  } catch {
    document.getElementById('serverState').textContent = 'offline';
    sendBtn.disabled = true;
    sendBtn.textContent = 'Send';
  }
}



async function pollReceive() {
  try {
    const res = await fetch('/api/receive');
    if (!res.ok) return;
    const { message, quality } = await res.json();

    const key = `${message.from}|${message.message}|${message.timestamp || ''}`;
    const isMine = message.from === user;

    // Only append once, with correct status
    appendMessage({
      from: message.from,
      message: message.message,
      status: isMine ? 'synced' : 'received',
      key
    });

    if (!isMine) showNotification();

  } catch (e) {
    console.warn('Receive failed', e);
  }
}

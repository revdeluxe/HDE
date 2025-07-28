// static/app.js

// ——————————————————————————————————
// Constants & State

const POLL_INTERVAL_MS = 3000;
const seenMessages    = new Set();
let unreadCount       = 0;
let sendBtn;
let user      = null;
let fileName  = 'message.json';  // JSON file to fetch messages from

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

      // 2) Re-fetch full message list to sync
      await pollMessages();

      // 3) Mark this one synced
      msgEl.classList.replace('sent', 'synced');
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
  pollMessages();

  // Poll periodically
  setInterval(() => {
    refreshStatus();
    pollMessages();
  }, POLL_INTERVAL_MS);
});

// ——————————————————————————————————
// Polling & Status

async function refreshStatus() {
  fetch('/api/status')
    .then(r => r.json())
    .then(data => {
      Object.entries(data).forEach(([key, value]) => {
        const el = document.getElementById(`status-${key}`);
        if (el) {
          el.textContent = value == null ? 'N/A' : value;
        } else {
          console.warn(`No element for status-${key}`);
        }
      });
    })
    .catch(e => console.error('Status refresh failed', e));
}


async function pollMessages() {
  try {
    const res = await fetch(`/api/messages/${fileName}`);
    updateHttpStatus(res);
    if (!res.ok) return;

    const allMessages = await res.json();
    allMessages.forEach(msg => {
      const key    = msg.id || `${msg.from}|${msg.message}|${msg.ts}`;
      const isMine = msg.from === user;
      appendMessage({
        from:    msg.from,
        message: msg.message,
        status:  isMine ? 'synced' : 'received',
        key
      });
      if (!isMine) showNotification();
    });

    // Re-enable send button after syncing
    sendBtn.disabled    = false;
    sendBtn.textContent = 'Send';
  } catch (err) {
    console.warn('pollMessages() failed', err);
  }
}

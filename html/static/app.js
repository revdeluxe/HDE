console.log('app.js loaded');

function appendMessage({ from, message, status = 'received', id }) {
  const div = document.createElement('div');
  div.className = `message ${status}`;
  div.dataset.id = id;
  div.textContent = `${from}: ${message}`;
  document.getElementById('messages').append(div);
  scrollToBottom();
}

function scrollToBottom() {
  const c = document.getElementById('messages');
  c.scrollTop = c.scrollHeight;
}

async function loadMessages() {
  const startTime = performance.now();

  try {
    // fetch inbox
    const res = await fetch('/api/inbox');
    const msgs = await res.json();
    const container = document.getElementById('messages');
    container.innerHTML = '';
    msgs.forEach((m, i) =>
      appendMessage({
        ...m,
        status: m.from === getUserName() ? 'sent' : 'received',
        id: i
      })
    );

    // now perform the bi-directional ping
    const pingTime = performance.now();
    const pingRes = await fetch('/api/ping');
    const pingData = await pingRes.json();
    const pingRTT = performance.now() - pingTime;

    const pongStart = performance.now();
    const pongRes = await fetch('/api/pong', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_time: performance.now() / 1000 })
    });
    const pongData = await pongRes.json();
    const pongRTT = performance.now() - pongStart;

    const quality = getStreamQuality(pingRTT, pongData.latency * 1000);
    updateStreamQualityDisplay(quality, pingRTT, pongData.latency * 1000);
  } catch (e) {
    console.error('Error during message or latency fetch', e);
    updateStreamQualityDisplay('Offline', null, null);
  }
}



function getStreamQuality(linkBudget, snr) {
  // linkBudget in dBm+dBi (higher = better), snr in dB
  if (linkBudget > -80 && snr > 7)   return 'Excellent';
  if (linkBudget > -90 && snr > 5)   return 'Good';
  if (linkBudget > -100 && snr > 2)  return 'Fair';
  return 'Poor';
}


function updateStreamQualityDisplay(label, linkBudget, snr) {
  const el = document.getElementById('streamQuality');
  el.textContent = `${label}` +
    (linkBudget != null
      ? ` (${linkBudget.toFixed(1)} dBm+dBi / SNR ${snr.toFixed(1)} dB)`
      : '');
  el.className = `status stream-quality ${label}`;
}


function getUserName() {
  const match = document.cookie.match(/(?:^|;\s*)username=([^;]+)/);
  return match ? match[1] : 'Anonymous';
}

async function sendMessage(text) {
  const tempId = Date.now();
  appendMessage({ from: getUserName(), message: text, status: 'pending', id: tempId });
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: getUserName(), message: text })
    });
    if (!res.ok) throw new Error(res.status);
    div = document.querySelector(`.message[data-id="${tempId}"]`);
    div.classList.replace('pending', 'sent');
  } catch {
    const div = document.querySelector(`.message[data-id="${tempId}"]`);
    div.classList.replace('pending', 'error');
  }
}

async function loadAdminConfigs() {
  const panels = [
    ['/config/info',               'General Config'],
    ['/config/info/lora-gateway', 'LoRa Gateway'],
    ['/config/info/lora-device',  'LoRa Device'],
    ['/config/info/general', 'Backend General Info'],

  ];

  for (const [url, title] of panels) {
    try {
      const res = await fetch(url);
      const cfg = await res.json();

      const section = document.createElement('details');  // 🔑 create inside loop
      section.innerHTML = `
        <summary>⚙️ ${title}</summary>
        <pre contenteditable="true" spellcheck="false" data-endpoint="${url.replace('/info', '')}">${JSON.stringify(cfg, null, 2)}</pre>
        <button>💾 Save</button>
      `;

      section.querySelector('button').onclick = async () => {
        const pre = section.querySelector('pre');
        try {
          const newData = JSON.parse(pre.innerText);
          const resp = await fetch(pre.dataset.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newData)
          });
          const result = await resp.json();
          alert(`✅ ${title} updated`);
        } catch (err) {
          alert(`❌ Invalid JSON or failed to update`);
        }
      };

      document.getElementById('configPanel').appendChild(section);
    } catch (err) {
      console.error(`❌ Failed to load config: ${title}`, err);
    }
  }
}


document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM ready');
  const form = document.getElementById('messageForm');
  const input = document.getElementById('messageInput');
  const es = new EventSource('/api/stream');
  es.addEventListener('message', e => { /* appendMessage */ });
  es.onerror = () => console.warn('SSE failed');



  form.addEventListener('submit', e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendMessage(text);
  });

  // 2) subscribe to SSE for new messages
  if (window.EventSource) {
    const es = new EventSource('/api/stream');
    es.addEventListener('message', e => {
      const msg = JSON.parse(e.data);
      appendMessage({
        ...msg,
        status: msg.from === getUserName() ? 'sent' : 'received',
        id: Date.now()
      });
    });
  } else {
    setInterval(() => {
      loadMessages();
      loadLoraMetrics();
    }, 5000);
  }
});

  
// 1) Helper to read a cookie
function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )'+ name +'=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}

// 2) Fill username if present
const user = getCookie('username');
if (user) {
  document.getElementById('usernameField').textContent = user;
  document.getElementById('userName').style.display = 'inline';
}

fetch('/config/info')
  .then(r => r.json())
  .then(info => {
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };

    set('serverName', info.hostname ?? 'Unknown');
    set('streamQuality', info.stream_quality ?? 'N/A');
    set('firmware-version', info.firmware_version ?? '—');
  })
  .catch(() => {
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };

    set('serverName', 'Unknown');
    set('streamQuality', 'Backend not available');
      set('firmware-version', 'Lora module not available');
  });
  
  // after "DOM ready"�
const es = new EventSource('/api/stream');

es.addEventListener('message', e => { /* existing chat logic */ });

es.addEventListener('quality', e => {
  const { rssi, snr, gain_dbi } = JSON.parse(e.data);
  const linkBudget = rssi + gain_dbi;
  const label = getStreamQuality(linkBudget, snr);
  updateStreamQualityDisplay(label, linkBudget, snr);

  // auto-send over LoRa when link is good
  if (label === 'Excellent' || label === 'Good') {
    // grab any unsent messages (status 'pending') in the DOM
    document
      .querySelectorAll('.message.pending')
      .forEach(div => {
        const text = div.textContent.split(': ').slice(1).join(': ');
        fetch('/api/send_lora', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ from: getUserName(), message: text })
        })
        .then(res => res.ok
          ? div.classList.replace('pending','sent')
          : div.classList.replace('pending','error')
        )
        .catch(() => div.classList.replace('pending','error'));
      });
  }
});

es.onerror = () => console.warn('SSE failed');

form.addEventListener('submit', e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  appendMessage({
    from: getUserName(),
    message: text,
    status: 'pending',
    id: Date.now()
  });
});



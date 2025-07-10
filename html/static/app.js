console.log('app.js loaded');

function appendMessage({from,message,status,id}) {
  if (document.querySelector(`.message[data-id="${id}"]`)) return;
  const d = document.createElement('div');
  d.className = `message ${status}`;
  d.dataset.id = id;
  d.textContent = `${from}: ${message}`;
  document.getElementById('messages').append(d);
  d.scrollIntoView({behavior:'smooth'});
}

function getCookie(n){
  const m=document.cookie.match(new RegExp('(?:^|; )'+n+'=([^;]+)'));
  return m?decodeURIComponent(m[1]):'';
}

function getUserName(){return getCookie('username')||'Anonymous';}

function sendMessage(text){
  const id = Date.now().toString();
  appendMessage({from:getUserName(),message:text,status:'pending',id});
  fetch('/api/send',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({from:getUserName(),message:text})
  }).catch(_=>{ 
    const e = document.querySelector(`.message[data-id="${id}"]`);
    if(e) e.classList.replace('pending','error');
  });
}

document.addEventListener('DOMContentLoaded',()=>{
  // Set up SSE
  const es = new EventSource('/api/stream');

  es.addEventListener('message',e=>{
    const m=JSON.parse(e.data);
    appendMessage({...m,status:m.origin===window.location.hostname?'sent':'received',id:m.id});
  });

  es.addEventListener('confirm',e=>{
    const d=document.querySelector(`.message[data-id="${e.data}"]`);
    if(d){
      d.classList.replace('pending','confirmed');
      d.textContent += ' ?';
    }
  });

  es.addEventListener('sync:start',_=>{
    document.getElementById('sendBtn').disabled=true;
  });
  es.addEventListener('sync:end',_=>{
    document.getElementById('sendBtn').disabled=false;
  });

  // Form handler
  document.getElementById('messageForm').addEventListener('submit',e=>{
    e.preventDefault();
    const inp=document.getElementById('messageInput');
    const t=inp.value.trim(); if(!t)return;
    inp.value=''; sendMessage(t);
  });
});

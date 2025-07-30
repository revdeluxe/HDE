let messagesContainer = document.getElementById("messagesContainer");
let checksum = "";
let conversation = "messages.json";

function messageStatus(status) {
  const statusElement = document.getElementById("status-busy");
  if (!statusElement) return;
  if (status === "sending") {
    statusElement.textContent = "Sending...";
    statusElement.className = "pending";
  } else if (status === "LoRa failed") {
    statusElement.textContent = "LoRa failed";
    statusElement.className = "error";
  } else if (status === "sent") {
    statusElement.textContent = "Message sent successfully";
    statusElement.className = "synced";
  } else {
    statusElement.textContent = "General Failure";
    statusElement.className = "error";
  }
}

async function getChecksum() {
  try {
    const response = await fetch("/api/checksum");
    if (!response.ok) throw new Error("Failed to fetch checksum");
    const data = await response.json();
    return data.checksum || "";
  } catch (error) {
    console.error("Checksum fetch error:", error);
    return "";
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

function usernamePrompt(defaultUsername) {
  let uname = getCookie("username");
  if (!uname) {
    uname = prompt("Please enter your username:") || defaultUsername;
    if (uname) {
      document.cookie = `username=${encodeURIComponent(uname)}; path=/;`;
    }
  }
  document.getElementById("UsernameField").value = uname || (document.cookie = `username=${encodeURIComponent(uname)};`);
  return uname;
}

async function send() {
  const from = document.getElementById("UsernameField").value;
  const message = document.getElementById("messageInput").value;
  if (!message.trim()) return;

  const checksum = await getChecksum();

  messageStatus("sending");

  fetch(`/api/send`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      message,
      checksum,
    }),
  })
    .then(response => {
      if (!response.ok) throw new Error("Send failed");
      return response.json();
    })
    .then(data => {
      console.log("Message sent:", data);
      messageStatus("sent");
      document.getElementById("messageInput").value = ""; // clear input
      fetchMessages(); // Refresh messages
    })
    .catch(error => {
      console.error("Send error:", error);
      messageStatus("LoRa failed");
    });
}

function fetchMessages() {
  fetch(`/api/messages/${conversation}`)
    .then(response => {
      if (!response.ok) throw new Error("Fetch failed");
      return response.json();
    })
    .then(data => {
      const messagesContainer = document.getElementById("messages");
      if (!messagesContainer) {
        console.error("Element with ID 'messages' not found.");
        return;
      }

      messagesContainer.innerHTML = ""; // Clear previous

      const from_user = getCookie("username");

      data.data.forEach(entry => {
        const from = entry.from || "Unknown";
        const chunk = entry.chunk || [];

        chunk.forEach(msg => {
          const messageElement = document.createElement("div");
          messageElement.innerHTML = `<strong>${from}</strong>: ${msg.message}`;
          messageElement.className = from === from_user ? "sent" : "messageReceived";
          messagesContainer.appendChild(messageElement);
        });
      });
    })
    .catch(error => {
      console.error("Error loading messages:", error);
    });
}

function fetchMessagesLoRa(){
  fetch('/api/receive', {
    method: 'POST',
  })
    .then(response => {
      if (!response.ok) throw new Error("Fetch failed");
      return response.json();
    })
    .then(data => {
      console.log("LoRa messages:", data);
      alert(JSON.stringify(data));
    })
    .catch(error => {
      console.error("Error fetching LoRa messages:", error);
    });
}


document.addEventListener("DOMContentLoaded", async () => {
  const defaultUsername = "Guest";
  const user = usernamePrompt(defaultUsername);

  const sendButton = document.getElementById("sendButton");
  if (sendButton) {
    sendButton.addEventListener("click", (event) => {
      event.preventDefault();
      send();
    });
  }

  const messageInput = document.getElementById("messageInput");
  if (messageInput) {
    messageInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        send();
      }
    });
  }

  fetchMessages();
  fetchMessagesLoRa();
  setInterval(fetchMessages, 5000);
});

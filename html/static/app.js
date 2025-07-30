// static/app.js
let from = document.getElementById("UsernameField").value;
let messagesContainer = document.getElementById("messagesContainer");
let checksum = "";

function getCookie(name) {
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + name + '=([^;]*)')
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function usernamePrompt() {
  from = getCookie("username") || from;
  if (!from || from === "Anonymous") {
    from = prompt("Please enter your username:");
  }
  if (from) {
    document.getElementById("UsernameField").value = from;
  }
  return from;
}

function send(){
  const message = document.getElementById("messageInput").value;
  if (!message) return;

  fetch(`/api/send/${encodeURIComponent(message)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCookie("csrftoken"),
    },
    body: JSON.stringify(
      { from },
      { message },
      { checksum }
    ),
  })
  .then(response => {
    if (!response.ok) throw new Error("Network response was not ok");
    return response.json();
  })
  .then(data => {
    console.log("Message sent successfully:", data);
  })
  .catch(error => {
    console.error("Error sending message:", error);
  });
}

function fetchMessages() {
  fetch("/api/messages")
    .then(response => {
      if (!response.ok) throw new Error("Network response was not ok");
      return response.json();
    })
    .then(data => {
      messagesContainer.innerHTML = ""; // Clear previous messages
      data.forEach(msg => {
        const messageElement = document.createElement("div");
        messageElement.className = "message";
        messageElement.innerHTML = `<strong>${msg.sender}</strong>: ${msg.message} <span class="timestamp">${new Date(msg.timestamp * 1000).toLocaleTimeString()}</span>`;
        messagesContainer.appendChild(messageElement);
      });
    })
    .catch(error => {
      console.error("Error fetching messages:", error);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  usernamePrompt();
  document.getElementById("sendButton").addEventListener("click", () => {
    try {
      message.preventDefault();
      send();
    } catch (error) {
      console.error("Error sending message:", error);
    }
  });
  document.getElementById("messageInput").addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      e.preventDefault(); // Prevent form submission
      try {
        send();
      } catch (error) {
        console.error("Error sending message on Enter key press:", error);
      }
    }
  });
  fetchMessages();
  setInterval(fetchMessages, 5000); // Fetch messages every 5 seconds
});
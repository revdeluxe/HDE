// static/app.js
let from = document.getElementById("UsernameField").value;
let messagesContainer = document.getElementById("messagesContainer");

function messageStatus(status) {
  const statusElement = document.getElementById("status-busy");
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

function getChecksum() {
  let checksum = "";
  fetch("/api/checksum")
    .then(response => {
      if (!response.ok) throw new Error("Network response was not ok");
      return response.json();
    })
    .then(data => {
      checksum = data.checksum;
    })
    .catch(error => {
      console.error("Error fetching checksum:", error);
    });
  return checksum;
}

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

function sentMessage(name) {
    const messageElement = document.createElement("div");
    messageElement.className = "message";
    messageElement.innerHTML = `<strong>${name}</strong>: <span class="status">Message sent successfully</span>`;
    messagesContainer.appendChild(messageElement);
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
        let from_user = msg.from_user;
        let msgStatus = msg.msg_status;
        const messageElement = document.createElement("div");
        if (msg.from === from_user) { // Sent message
          messageElement.innerHTML = `<strong>${msg.from}</strong>: ${msg.message}`;
          messageElement.className = "sent";
          messageStatus(msgStatus);
          const statusElement = document.createElement("span");
          statusElement.className = "status";
          statusElement.innerHTML = `<span class="status">Message sent successfully</span>`;
          messagesContainer.appendChild(statusElement);
          messagesContainer.appendChild(messageElement);
        } else { // Received message
          messageElement.innerHTML = `<strong>${msg.from}</strong>: ${msg.message}`;
          messageElement.className = "messageReceived";
          messagesContainer.appendChild(messageElement);
        }
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
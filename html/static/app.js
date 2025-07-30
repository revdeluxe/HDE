// static/app.js
let from = document.getElementById("UsernameField").value;
let messagesContainer = document.getElementById("messagesContainer");
let cookie_name = getCookie("username");
let checksum = "";

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

function usernamePrompt(username) {
  let uname = getCookie("username");
  if (uname) {
    document.getElementById("UsernameField").innerHTML = uname;
    document.getElementById("UsernameField").value = uname;
  } else {
    uname = prompt("Please enter your username:") || username;
    if (uname) {
      document.cookie = `username=${encodeURIComponent(uname)}; path=/;`;
      document.getElementById("UsernameField").innerHTML = uname;
      document.getElementById("UsernameField").value = uname;
    }
  }
  return uname;
}

function send(){
  const message = document.getElementById("messageInput").value;
  schecksum = getChecksum();
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
      { schecksum }
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
  fetch("/api/messages/")
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
  let sendButton = document.getElementById("sendButton");
  if (sendButton) {
    sendButton.addEventListener("click", (event) => {
      try {
        event.preventDefault();  // <-- fixed: was `message.preventDefault()`
        send();
      } catch (error) {
        console.error("Error sending message:", error);
      }
    });
  } else {
    console.warn("sendButton not found in DOM.");
  }
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
  getChecksum();
  usernamePrompt(cookie_name);
  fetchMessages();
  setInterval(fetchMessages, 5000); // Fetch messages every 5 seconds
});
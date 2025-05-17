function pollLora() {
    fetch('/lora')
        .then(res => res.json())
        .then(data => {
            logToConsole(`[POLL] ${new Date(data.timestamp * 1000).toLocaleTimeString()} - ${data.message}`);
        })
        .catch(err => {
            logToConsole(`[ERROR] ${err.message}`, 'error');
        });
}

// Poll every 30 seconds
setInterval(pollLora, 30000);
pollLora(); // Initial poll on load

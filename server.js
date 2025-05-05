const express = require('express');
const PouchDB = require('pouchdb');
const { Server } = require('http');
const { createServer } = require('asterisk-ami');

require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

// Serve static files from ./html directory
app.use('/', express.static('./html'));

// Initialize PouchDB
const db = new PouchDB('database');

// Asterisk AMI connection
const ami = createServer({
    host: process.env.ASTERISK_HOST || '127.0.0.1',
    port: process.env.ASTERISK_PORT || 5038,
    username: process.env.ASTERISK_USERNAME || 'admin',
    secret: process.env.ASTERISK_SECRET || 'password',
});

ami.on('connect', () => {
    console.log('Connected to Asterisk AMI');
});

ami.on('event', (event) => {
    console.log('AMI Event:', event);
});

ami.on('error', (err) => {
    console.error('AMI Error:', err);
});

// Start the server
const server = Server(app);
server.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
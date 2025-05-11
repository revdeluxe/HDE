import { Pool } from 'pg';
import AmiClient from 'asterisk-ami';
import dotenv from 'dotenv';
import express from 'express';
const app = express();
const port = 3001;

app.use(express.json());

app.get('/data', async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM your_table_name');
        res.json(result.rows);
    } catch (err) {
        console.error('Error executing query:', err.stack);
        res.status(500).send('Internal Server Error');
    }
});

app.post('/login', async (req, res) => {
    const { username, passphrase } = req.body;
    try {
        const result = await pool.query(
            'SELECT * FROM "user".user_info WHERE username = $1 AND passphrase = $2',
            [username, password]
        );
        if (result.rows.length > 0) {
            const user = result.rows[0];

            // Update user status to online
            await pool.query(
                'UPDATE "user".user_info SET status = $1 WHERE uid = $2',
                ['online', user.uid]
            );

            // Log the successful login attempt
            await pool.query(
                `INSERT INTO "user".log_attempts (uid, success, ip_address, browser) 
                 VALUES ($1, $2, $3, $4)`,
                [user.uid, true, req.ip, req.headers['user-agent']]
            );

            res.json({ success: true, user });
        } else {
            // Log the failed login attempt
            await pool.query(
                `INSERT INTO "user".log_attempts (uid, success, ip_address, browser) 
                 VALUES ($1, $2, $3, $4)`,
                [null, false, req.ip, req.headers['user-agent']]
            );

            res.status(401).json({ success: false, message: 'Invalid credentials' });
        }
    } catch (err) {
        console.error('Error executing login query:', err.stack);
        res.status(500).send('Internal Server Error');
    }
});

app.post('/log_attempts', async (req, res) => {
    const { uid, success, ip_address, browser } = req.body;
    try {
        const result = await pool.query(
            `INSERT INTO "user".log_attempts (uid, success, ip_address, browser) 
             VALUES ($1, $2, $3, $4) RETURNING *`,
            [uid, success, ip_address, browser]
        );
        res.json({ success: true, log: result.rows[0] });
    } catch (err) {
        console.error('Error logging attempt:', err.stack);
        res.status(500).send('Internal Server Error');
    }
});

app.listen(port, () => {
    console.log(`Server is running on port ${port}`);
});
dotenv.config();

const ami = new AmiClient({ reconnect: true });

const pool = new Pool({
    user: process.env.PG_USER || 'postgres',
    host: process.env.PG_HOST || '127.0.0.1',
    database: process.env.PG_DATABASE || 'master',
    password: process.env.PG_PASSWORD || 'admin',
    port: process.env.PG_PORT || 5432,
});

pool.connect((err, _, release) => {
    if (err) {
        console.error('Error connecting to PostgreSQL:', err.stack);
    } else {
        console.log('Connected to PostgreSQL');
        release();
    }
});

// AMI connection
ami.connect({
    username: process.env.ASTERISK_USERNAME || 'admin',
    secret: process.env.ASTERISK_SECRET || 'password',
    host: process.env.ASTERISK_HOST || '127.0.0.1',
    port: process.env.ASTERISK_PORT || 5038,
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

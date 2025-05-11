import './App.css';
import React, { useState } from 'react';

function App() {
  const [page, setPage] = useState('landing');

  React.useEffect(() => {
    const fetchSystemPerformance = async () => {
      try {
        const response = await fetch('http://localhost:5432/system-performance');
        if (!response.ok) {
          console.error('Failed to fetch system performance data');
          return;
        }
        const data = await response.json();
        document.getElementById('ram-usage').textContent = `${data.ramUsed}GB / ${data.ramTotal}GB`;
        document.getElementById('cpu-load').textContent = `${data.cpuLoad}%`;
      } catch (error) {
        console.error('Error fetching system performance:', error);
      }
    };

    fetchSystemPerformance();
  }, []);

  const renderPage = () => {
    switch (page) {
      case 'landing':
        return (
          <div className="Landing">
            <h1>Welcome to the Landing Page</h1>
            <button onClick={() => setPage('login')}>Login</button>
          </div>
        );
      case 'login':
        return (
          <div className="Login">
            <h1>Login</h1>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const username = e.target.elements.username.value.trim();
                const passphrase = e.target.elements.passphrase.value.trim();

                if (!username || !passphrase) {
                  alert('Please fill in both username and password.');
                  return;
                }

                try {
                  const response = await fetch('http://localhost:3001/login', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, passphrase }),
                  });

                  if (!response.ok) {
                    alert('Error during login. Please try again.');
                    return;
                  }

                  const data = await response.json();

                  if (data.success) {
                    setPage('admin-panel');
                  } else {
                    alert('Invalid credentials');
                  }
                } catch (error) {
                  console.error('Error:', error);
                  alert('Failed to connect to the server. Please check your connection.');
                }
                }}
                >
              <input type="text" name="username" placeholder="Username" required />
              <input type="password" name="passphrase" placeholder="Password" required />
              <button type="submit">Login</button>
            </form>
          </div>
        );
      case 'admin-panel':
        return (
          <div className="AdminPanel">
        <h1>Admin Panel</h1>
        <p>Status: Online</p>
        <button onClick={() => setPage('landing')}>Logout</button>

        <div className="Tools">
          <h2>Tools</h2>}
              <div className="UserManagement">
                <h3>User Management</h3>
                <table>
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Email</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>JohnDoe</td>
                      <td>john@example.com</td>
                      <td>
                        <button>Edit</button>
                        <button>Delete</button>
                        <button>Ban</button>
                      </td>
                    </tr>
                    {/* Add more rows as needed */}
                  </tbody>
                </table>
                <button>Add User</button>
              </div>

              {/* VOIP Dialer */}
              <div className="VoipDialer">
                <h3>VOIP Dialer</h3>
                <input type="text" placeholder="Enter number" />
                <button>Dial</button>
              </div>

              {/* VOIP Contact Explorer */}
              <div className="VoipContactExplorer">
                <h3>VOIP Contact Explorer</h3>
                <ul>
                  <li>Contact 1</li>
                  <li>Contact 2</li>
                  <li>Contact 3</li>
                  {/* Add more contacts as needed */}
                </ul>
              </div>
            </div>
          </div>
        );
      default:
        return <div>Page not found</div>;
    }
  };

  return <div className="App">{renderPage()}</div>;
}
export default App;

import { useState, useEffect } from "react";
import Cookies from "js-cookie";

// Import pages
import WelcomePage from "./components/pages/WelcomePage";
import LoginPage from "./components/pages/LoginPage";
import AdminPanel from "./components/pages/AdminPanel";
import AboutPage from "./components/pages/AboutPage";
import DialerPage from "./components/pages/DialerPage";
import ExplorerPage from "./components/pages/ExplorerPage";
import UserManagementPage from "./components/pages/UserManagementPage";


function App() {
  const [currentPage, setCurrentPage] = useState('welcome');
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const loginStatus = Cookies.get('loggedIn') === 'true';
    setIsLoggedIn(loginStatus);
  }, []);

  const switchPage = (page) => {
    if (page === 'logout') {
      Cookies.remove('loggedIn');
      setIsLoggedIn(false);
      setCurrentPage('welcome');
    } else {
      setCurrentPage(page);
    }
  };

  return (
    <>
      {currentPage === 'welcome' && <WelcomePage switchPage={switchPage} />}
      {currentPage === 'login' && <LoginPage switchPage={switchPage} />}
      {currentPage === 'admin' && isLoggedIn && <AdminPanel switchPage={switchPage} />}
      {currentPage === 'about' && <AboutPage switchPage={switchPage} />}
      {currentPage === 'dialer' && <DialerPage switchPage={switchPage} />}
      {currentPage === 'explorer' && <ExplorerPage switchPage={switchPage} />}
      {currentPage === 'users' && <UserManagementPage switchPage={switchPage} />}
    </>
  );
}

export default App;

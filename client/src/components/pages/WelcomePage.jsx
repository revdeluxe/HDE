// src/pages/WelcomePage.jsx
import { Button } from "../ui/button"; // adjust if needed

export default function WelcomePage({ switchPage }) {
  return (
    <div className="bg-green-900 text-white p-4 h-screen flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-6">WELCOME TO HYBRID EMERCOM</h1>
      <div className="flex gap-4 mb-4">
        <Button onClick={() => switchPage('login')}>Log In</Button>
        <Button onClick={() => switchPage('about')}>About Us</Button>
      </div>
    </div>
  );
}

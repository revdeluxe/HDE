import React from 'react';
//import './button.css'; // You can skip this if you add styles globally

export const Button = ({ children, onClick, className = '', type = 'button' }) => {
  return (
    <button
      type={type}
      className={`btn ${className}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
};

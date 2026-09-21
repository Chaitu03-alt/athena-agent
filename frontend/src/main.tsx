import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { CyberpunkHUD } from './CyberpunkHUD';

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <CyberpunkHUD />
    </React.StrictMode>
  );
}

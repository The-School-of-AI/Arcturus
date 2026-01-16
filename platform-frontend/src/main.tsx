import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Branded Dialog Overrides
if ((window as any).electronAPI?.confirm) {
  window.confirm = (message?: string) => (window as any).electronAPI.confirm(message || "");
  window.alert = (message?: any) => (window as any).electronAPI.invoke('dialog:alert', { message: String(message) });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

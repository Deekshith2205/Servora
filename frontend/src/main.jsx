import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import LandingPage from './pages/LandingPage.jsx'

const path = window.location.pathname;
const isApp = path.startsWith('/app');

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isApp ? <App /> : <LandingPage />}
  </StrictMode>,
)

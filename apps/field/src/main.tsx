import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { applyRaje3 } from './theme';
import './index.css';

applyRaje3();
createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
);

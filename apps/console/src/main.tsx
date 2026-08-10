import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import { App } from './App';
import { Visit } from './screens/Visit';
import { applyRaje3 } from './brand/theme';
import './index.css';

// ROUTES MATCH nav.ts BY PATH. The nav decides what is OFFERED; the router decides what EXISTS.
// Keeping them separate is deliberate: a person who types a URL for a section his capabilities do
// not reach gets the screen, and the screen gets nothing from the catalogue — which is the same
// answer the server would give, arrived at without the client pretending to be the guard.
const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Visit /> },
      { path: 'visit', element: <Visit /> },
    ],
  },
]);

applyRaje3();
createRoot(document.getElementById('root')!).render(
  <StrictMode><RouterProvider router={router} /></StrictMode>,
);

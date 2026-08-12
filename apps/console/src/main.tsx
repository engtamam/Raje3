import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import { App } from './App';
import { Visit } from './screens/Visit';
import { Home } from './screens/Home';
import { Customers } from './screens/CustomersRoute';
import { Customer } from './screens/CustomerRoute';
import { Account } from './screens/AccountRoute';
import { Services } from './screens/ServicesRoute';
import { Messages } from './screens/MessagesRoute';
import { Points } from './screens/PointsRoute';
import { Team } from './screens/TeamRoute';
import { Local } from './screens/LocalRoute';
import { AuthI18nProvider } from '@base-ui/auth/i18n';
import { BlockDocI18nProvider } from '@base-ui/components/blockdoc';
import { ImtithalakUiProvider } from '@base-ui/design-system/shell';
import { arabicAuth, arabicBlockDoc, arabicShared } from './i18n';
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
      { index: true, element: <Home /> },
      { path: 'visit', element: <Visit /> },
      { path: 'customers', element: <Customers /> },
      // NOT A SECTION IN THE NAV, and deliberately: it is reached BY opening a
      // customer, never by choosing it. A tenth nav entry for a screen that needs an
      // id would be an entry that cannot be pressed.
      { path: 'customers/:id', element: <Customer /> },
      { path: 'account', element: <Account /> },
      { path: 'services', element: <Services /> },
      { path: 'messages', element: <Messages /> },
      { path: 'points', element: <Points /> },
      { path: 'team', element: <Team /> },
      { path: 'shop', element: <Local /> },
    ],
  },
], {
  // AND THE ROUTER TOO — from the same value, never a second literal. The app is mounted under a
  // prefix, so a route declared as '/visit' is really '/app/visit'; a router that does not know
  // that matches nothing and renders the not-found branch on every screen, on a page whose assets
  // all loaded correctly. BASE_URL carries the trailing slash and basename must not.
  basename: import.meta.env.BASE_URL.replace(/\/$/, ''),
});

applyRaje3();
createRoot(document.getElementById('root')!).render(
  // THE PROVIDER WRAPS THE WHOLE APP, not just the door. The legal gate uses the kit's
  // AcceptTerms and lives inside the shell — a provider around the sign-in screen alone would
  // leave `auth.legal.*` raw on the one screen a person must read before agreeing to it.
  <StrictMode>
    {/* THREE SEAMS, THREE PROVIDERS. The kit has three independent i18n contexts and every one of
        them degrades to printing the raw key. Wrapping one and calling it done is how
        `auth.otp.hint 0505536720` reached a real screen — and the pager and the document viewer
        were one navigation behind it. */}
    <ImtithalakUiProvider t={arabicShared}>
      <BlockDocI18nProvider value={arabicBlockDoc}>
        <AuthI18nProvider value={arabicAuth}>
          <RouterProvider router={router} />
        </AuthI18nProvider>
      </BlockDocI18nProvider>
    </ImtithalakUiProvider>
  </StrictMode>,
);

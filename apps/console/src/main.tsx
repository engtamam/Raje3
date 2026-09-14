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
import { Rating } from './screens/RatingRoute';
import { Coupons } from './screens/CouponsRoute';
import { Team } from './screens/TeamRoute';
import { Bookings } from './screens/BookingsRoute';
import { ShopScreen } from './screens/Shop';
import { Store } from './screens/StoreRoute';
import { Support } from './screens/SupportRoute';
import { AffiliatePortal } from './affiliates/AffiliatePortal';
import { AdminPortal } from './admin/AdminPortal';
import { Legal } from './screens/Legal';
import { AuthI18nProvider } from '@base-ui/auth/i18n';
import { BlockDocI18nProvider } from '@base-ui/components/blockdoc';
import { ImtithalakUiProvider } from '@base-ui/design-system/shell';
import { arabicAuth, arabicBlockDoc, arabicShared } from './i18n';
import { applyRaje3 } from './brand/theme';
import { installErrorReporter } from './lib/errorReporter';
import './index.css';

// AFFILIATES.<DOMAIN> AND ADMIN.<DOMAIN> ARE DIFFERENT HOSTS, NOT DIFFERENT DEPLOYS. The edge
// (deploy/edge/edge.json) puts both hostnames on the same certificate and the same site block as
// the shop's own domain — this image is still what answers for either (see bring-up.sh). What
// changes is which tree we mount: neither the affiliate nor the admin hostname has a shop, a
// branch, an operator PIN, or any of what <App/> fetches on boot for its own audience, so each
// gets its own router root at '/' rather than living under '/app/…'.
const isAffiliateHost = typeof window !== 'undefined' && window.location.hostname.startsWith('affiliates.');
const isAdminHost = typeof window !== 'undefined' && window.location.hostname.startsWith('admin.');

// ROUTES MATCH nav.ts BY PATH. The nav decides what is OFFERED; the router decides what EXISTS.
// Keeping them separate is deliberate: a person who types a URL for a section his capabilities do
// not reach gets the screen, and the screen gets nothing from the catalogue — which is the same
// answer the server would give, arrived at without the client pretending to be the guard.
const shopRouter = createBrowserRouter([
  // A SIBLING OF '/', NOT A CHILD — deliberately outside <App>. <App> shows the door to anyone
  // signed out, and a legal document has to render for exactly that person: someone deciding
  // whether to sign up at all, or a shop's customer who has never had an account.
  { path: 'legal/:slug', element: <Legal /> },
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Home /> },
      { path: 'visit', element: <Visit /> },
      { path: 'bookings', element: <Bookings /> },
      { path: 'customers', element: <Customers /> },
      // NOT A SECTION IN THE NAV, and deliberately: it is reached BY opening a
      // customer, never by choosing it. A tenth nav entry for a screen that needs an
      // id would be an entry that cannot be pressed.
      { path: 'customers/:id', element: <Customer /> },
      { path: 'account', element: <Account /> },
      { path: 'services', element: <Services /> },
      { path: 'messages', element: <Messages /> },
      { path: 'points', element: <Points /> },
      { path: 'rating', element: <Rating /> },
      { path: 'coupons', element: <Coupons /> },
      { path: 'team', element: <Team /> },
      // «محلّي»'s OWN route (nav.ts::SHOP_PATH's own note explains why it is no longer also the
      // index route) — the page «اليوم» and «محلّي» became. Bookmarks, links in messages and the
      // e2e suite all use this path directly.
      { path: 'shop', element: <ShopScreen /> },
      // «متجر التطبيقات» — the name four screens print, given the address it never had. It renders
      // the selling pane of «حسابي» rather than a second copy of it; `/account?tab=billing` still
      // answers, for every link already sent.
      { path: 'store', element: <Store /> },
      { path: 'support', element: <Support /> },
    ],
  },
  // OUTSIDE <App/> ON PURPOSE. A marketer has no shop, no branch, no operator PIN and no action
  // catalogue — everything <App/> fetches on mount for the shop's own audience. A route nested
  // under it would either fetch that catalogue anyway (a 401 for an audience that never has a
  // shop token) or need <App/> itself to grow a "which product is this" branch. Its own tree,
  // its own session store (affiliates/session.ts) — see AffiliatePortal.tsx for why.
  //
  // STILL REGISTERED HERE TOO, on the shop's own domain — a link sent before the subdomain
  // existed, or anyone who never repointed DNS, must keep landing on the portal.
  {
    path: 'affiliates/*',
    element: <AffiliatePortal />,
  },
  // SAME REASONING, ONE ROUTE LOWER: a link sent before admin.<domain> existed, or an operator
  // who never repointed DNS, must still reach the panel from the shop's own domain.
  {
    path: 'admin/*',
    element: <AdminPortal />,
  },
], {
  // AND THE ROUTER TOO — from the same value, never a second literal. The app is mounted under a
  // prefix, so a route declared as '/visit' is really '/app/visit'; a router that does not know
  // that matches nothing and renders the not-found branch on every screen, on a page whose assets
  // all loaded correctly. BASE_URL carries the trailing slash and basename must not.
  basename: import.meta.env.BASE_URL.replace(/\/$/, ''),
});

// ITS OWN ROOT, on the affiliate hostname — not '/app'. A marketer's link is
// `affiliates.<domain>/…`, never `affiliates.<domain>/app/…`, so basename must match what the
// edge actually put them on rather than reusing BASE_URL.
const affiliateRouter = createBrowserRouter([
  // SAME REASONING AS shopRouter's own legal route — a marketer deciding whether to accept the
  // affiliate agreement needs to read it before he has a session, on his own hostname.
  { path: 'legal/:slug', element: <Legal /> },
  { path: '/*', element: <AffiliatePortal /> },
], { basename: '/' });

// SAME REASONING AS affiliateRouter, one line down — admin.<domain>/… never admin.<domain>/app/….
const adminRouter = createBrowserRouter([
  { path: 'legal/:slug', element: <Legal /> },
  { path: '/*', element: <AdminPortal /> },
], { basename: '/' });

const router = isAffiliateHost ? affiliateRouter : isAdminHost ? adminRouter : shopRouter;

applyRaje3();
// BEFORE THE FIRST RENDER, and beside applyRaje3() because this is the one place on this bundle
// that runs exactly once for all three hostnames. A reporter installed inside a component would
// miss everything that threw on the way to mounting it — which is the class of failure that
// leaves an owner looking at a blank pane with nothing anywhere to look at afterwards.
installErrorReporter();
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

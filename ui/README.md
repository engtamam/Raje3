# ui/ — Raje3 portals

Backend is base-services + our `services/`; the UI is ours.

| app | who | main surface |
|---|---|---|
| `app`   | establishment | owner/manager dashboard + field-entry screen (< 5s per visit) |
| `admin` | platform team | Super Admin console (tenants, plans, support, system health) |

Separate origins, one design system. Arabic-first (RTL), theme accent from
`config/product.json`.

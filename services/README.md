# services/ — Raje3 product services

Our business logic — the part base-services will never build for us. Each service is
**generated from the base-services `_template`** and follows its discipline: hexagonal
(ports/adapters chosen by config), deny-by-default, **zero hardcoded** values, its own
tests, its own security gate, its own deploy values. No cross-service imports.

Platform capabilities (auth, tenancy, authz, audit, notification transport, jobs,
analytics, wallet, billing, storage, gateway) are **not** built here — those are
base-services images we run and configure.

| service | owns | phase |
|---|---|---|
| `operations` | end customers, assets, service records, operators + PIN, field entry | MVP |
| `reminders`  | reminder rules, adaptive learning, next-due computation | MVP |
| `catalog`    | services, dynamic fields, template mapping | MVP |
| `loyalty`    | points earn/redeem, thresholds, cross-branch balance | later |
| `campaigns`  | segmentation, campaign send, anti-ban pacing, opt-out gate | later |

Services are added one at a time, from `_template`, as the roadmap reaches them.

# data/ — the axes (content that grows without a deploy)

Adding a sector, a service, or a sector template is a **data change**, not a code change —
the same idea base-services and imtithal use for their catalogs. The `catalog` service
loads this; the engine stays fixed.

```
sectors/     one folder per sector: its services, dynamic fields, default reminder rules
templates/   message templates per category (UTILITY / MARKETING), sector-scoped
axes.json    the index tying them together
```

Content is authored and reviewed like code, but ships without rebuilding a service.

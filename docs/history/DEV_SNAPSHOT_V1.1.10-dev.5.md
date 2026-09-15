# V1.1.10-dev.5 — Development Snapshot

## Login branding visibility fix

- Fixed the AKSHARA SCHOOL branding panel rendering with insufficient contrast.
- Root cause: `bg-primary-950` was referenced while the Tailwind primary palette only defined shades through `900`.
- Added `primary.950` to the Tailwind palette and replaced the login branding panel with an explicit dark, high-contrast gradient.
- Improved AKSHARA SCHOOL title contrast, capability cards, technology-partner footer, decorative background and responsive presentation.
- Kept the account-type login flow unchanged.
- No database/schema change. Alembic head remains `020`.

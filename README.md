# Kakakin

**Every voice, further.** A multi-tenant campaign workspace for permission-based WhatsApp Business and SMS messages, with voluntary referral sharing.

## Implemented

- Responsive dashboard with original trumpet logo and generated brass-and-emerald artwork.
- Persistent Cloudflare D1 data: tenants, platform users, memberships, contacts, consent records, campaigns, templates, deliveries, referral links, workspace controls, audit events, and dispatch leases.
- Tenant-scoped authorization on API requests; platform super administrators, workspace administrators, campaign managers, and read-only viewers.
- Contact create/edit/delete, segments, CSV import/export, consent-source recording, unsubscribe/suppression, deduplication, and non-routable test contacts.
- Campaign drafts, static WhatsApp template selection, SMS body composition, sandbox dispatch, live dispatch confirmation, scheduled campaign authorization, and a background scheduler handler.
- Server-side provider adapters for Meta WhatsApp Cloud API and Twilio SMS, including signed delivery and STOP callbacks.
- Per-workspace pause control, daily live-send caps, contact frequency limits, serialized dispatch, and duplicate campaign dispatch prevention. Current batch size: 50 recipients.
- Referral landing pages with voluntary WhatsApp share links, visit counts, and join requests. Public join requests remain non-sendable until an administrator independently verifies number ownership and consent.
- Team access by email, tenant switching, tenant suspension, platform user suspension and role administration, audit exports, and provider configuration status.
- Web app manifest and app icons for browser installation. Native Android/iOS packages are not included.

## Deploy to your own server with Ansible

A self-hosted adapter is now included. See [ansible/README.md](ansible/README.md) for setup and operations, [ansible/deploy.yml](ansible/deploy.yml) for the playbook, and [scripts/deploy-server.sh](scripts/deploy-server.sh) for the one-command wrapper.

```bash
sudo bash scripts/deploy-server.sh --domain YOUR_REAL_DOMAIN --admin-email YOUR_ADMIN_EMAIL
```

The server path uses a Dockerized workerd/Miniflare runtime with persistent local SQLite state, a password/session authentication gateway, an explicit bootstrap administrator email, Nginx, Let's Encrypt, pre-update backups, and a background scheduler independent of web visits. It is a single-server adapter, not managed D1 or a replicated production cluster. The trusted gateway strips client-supplied identity headers before calling the Worker. Never expose the Worker runtime directly.

## Hosting and identity

The project is prepared for **ChatGPT Sites / Cloudflare Workers**, using the Vinext starter and its `sites()` build integration. `.openai/hosting.json` identifies the existing Site and D1 binding. Hosted authentication is supplied by Sites. The owner-private deployment grants the first authenticated owner super administrator access; later users require email-based membership.

**Do not expose the Worker directly without the trusted Sites authentication boundary.** Identity headers must be inserted by the trusted gateway and stripped from untrusted inbound traffic. The unwrapped Worker does not implement password authentication; the self-hosted adapter above supplies it.

The current Site starts private. Public provider callbacks and referral traffic need a supported public hosting/access configuration. Do not switch audience without explicitly reviewing access and bootstrap behavior. If adapting to another host, implement trusted authentication and an explicit bootstrap administrator allowlist before public launch.

## Development

```sh
npm install
npm run db:generate  # only after changing db/schema.ts
npm run build
npm run dev
```

Use the Sites skill's dependency installer and build helpers in the managed environment. Dependencies and lockfile use pnpm there.

Apply each local migration once, in order, after building:

```sh
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_reflective_loa.sql
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0001_unique_rocket_racer.sql
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0002_wandering_the_order.sql
```

Publishing through Sites applies hosted migrations separately. Never create tables at request time or replay already-applied migrations.

## Provider configuration

See `.env.example` for secret names. Live credentials were not supplied and live messages have not been sent. Configure secrets in the server environment; they must never enter client bundles, campaign text, source control, or logs.

**WhatsApp:** set `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, and `WHATSAPP_API_VERSION` to the version supported by your Meta app. Also configure `META_APP_SECRET` and `WEBHOOK_VERIFY_TOKEN`. Register `/api/webhooks/meta` for the verification handshake and message/status callbacks. Create and approve static message templates in Meta, then map the exact provider template name and language in Kakakin. The current adapter supports static templates without dynamic components. Live WhatsApp sends the approved provider template, not arbitrary campaign text. Preview matching template wording before dispatch.

**SMS:** set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM`. Register `/api/webhooks/twilio` for incoming messages and status callbacks. If a proxy changes request URLs, set `TWILIO_WEBHOOK_URL` to the exact registered URL used for signature verification. Configure Twilio's required sender registration and opt-out handling for your destination markets. The server appends your configured opt-out instruction to SMS bodies.

The current provider account is platform-wide; tenant records and authorization are isolated but provider billing/sender credentials are shared. Per-tenant provider accounts, billing subscriptions, and encrypted GUI secret provisioning are future work. Configure credentials through the hosting secret manager.

Callback signatures use HMAC-SHA256 for Meta and Twilio's classic HMAC-SHA1 validation with the exact URL and sorted form fields. The Twilio handler is for classic Auth Token signatures; shared-key signature-settings variants need a provider SDK upgrade. STOP suppresses that phone across workspaces sharing the same sender to avoid sending after a recipient unsubscribes.

## Scheduling

`worker/index.ts` exports a `scheduled` handler, and `vite.config.ts` declares a five-minute cron. The built Wrangler metadata carries that trigger. The handler selects due, explicitly authorized campaigns for active tenants and dispatches them through the same consent, pause, provider, and rate checks. A live scheduled campaign requires typing `SEND` when saving and enabling workspace live delivery. Platform publication may not activate cron triggers: verify the host's scheduler before relying on unattended delivery. Until verified, the GUI supports manual dispatch after the due time. Hosted Cloudflare cron execution has not been observed. The self-hosted gateway scheduler is separately exercised by its integration test.

Dispatch leases serialize tenant sends and expire after 15 minutes. A process termination after a provider accepts a message can leave a campaign in `sending`; investigate provider records before a manual database repair. Do not automatically retry an ambiguous send, as this can duplicate messages.

## Tests

```sh
node node_modules/typescript/bin/tsc --noEmit
npm run build
node tests/integration.mjs
node tests/server-auth.mjs
node tests/server-gateway.mjs
```

The integration script uses the managed pnpm Miniflare dependency to load the actual built Worker and an isolated ephemeral D1 database. It verifies authorization, tenant separation, consent evidence, duplicate prevention, sandbox ledger persistence, referral validation, pending referral verification, and fail-closed live delivery. No external messages are sent. Adjust the Miniflare import path if installing dependencies using another package manager.

## Contact CSV

Required: `name,phone`. Optional: `email,segment,consent,consent_source,channel,status`. Phone numbers use `+` plus international country code. `consent` accepts `true`, `1`, or `yes`; a non-empty source is mandatory. Channels: `WhatsApp`, `SMS`, or `Both`. Imports are bounded to 200 records. Review opt-in evidence before uploading. Synthetic test identifiers cannot be routed to a provider.

## Scope

Kakakin does not harvest WhatsApp address books, generate live recipients from number ranges, blindly message unverified numbers, or auto-send from personal WhatsApp accounts. Referrals are voluntary. Website visits and downloads do not constitute messaging consent.

Plan names are administrative labels; payment collection, automated number ownership verification, conversation inbox, advanced attribution, and native app-store builds are not implemented. Dashboard metrics come from saved records and distinguish simulation, provider acceptance, confirmed delivery, and failure. Referral visit counts are cookie-based, not identity-verified unique people. Policy copy in the GUI is a starting point and needs operator contact/retention details before public launch.

## Artwork

Original SVG trumpet mark: `public/favicon.svg`. Generated artwork: `public/kakakin-art.webp` (built-in image generation; compressed for delivery). Prompt: sculptural copper/brass ceremonial trumpet with emerald enamel, flowing green ribbons and pearl spheres representing voices connecting communities, warm ivory backdrop, African geometric detailing, premium tactile editorial 3D art; no text or UI. Icons: original mark rendered at 192 and 512 pixels.

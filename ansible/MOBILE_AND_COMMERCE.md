# Mobile, marketplace and platform controls

Run on the existing Olamidepanel host:

```sh
cd /opt/kakakin-bootstrap
git fetch origin main
git checkout --detach FETCH_HEAD
bash scripts/deploy-mobile.sh --admin-email dobcalldemo@gmail.com
```

This repairs/deploys Kakakin using the existing targeted repair playbook, then updates the existing africanappsstore.service using its code/database backups. It verifies public APK downloads and the catalog entry. It does not recreate the store database or replace its TLS/port. A hidden store listing remains hidden; a visibility decision is left to the store administrator. Both services must already be on this server, as in the supplied deployment context.

Public pages: /install, /terms, /privacy, /copyright. Signed-in marketplace: /marketplace. Super admin controls: /platform. Dashboard links preserve the selected tenant. Product drafts are tenant owned; publishing requires a super admin. Buyers see their own orders, workspace staff see their workspace orders, and platform admins see all. Only verified paid orders may be marked fulfilled. Platform users, workspace roles and suspensions remain in the original dashboard.

Integration secrets are encrypted with AES-GCM before D1 storage. The Ansible deployment generates /etc/kakakin/credentials.key separately from session.key; keep this key with database backups. Losing it makes stored credentials unreadable. Do not delete or casually rotate it. Self-hosted development falls back to the session secret if CREDENTIALS_KEY is omitted; Cloudflare deployments must provide their own 48+ character CREDENTIALS_KEY secret. Saved values are never returned through the API. A blank input preserves a saved value; Clear removes it. Only super admins can save credentials, with origin checks and audit events. Enabled GUI WhatsApp/Twilio settings override legacy environment settings, including disabling the provider.

## Payments

Paystack and Stripe hosted checkout are implemented. Start with provider test keys and configure the provider dashboard webhooks:

- https://kakakin.africandroid.world/api/payments/paystack (charge.success)
- https://kakakin.africandroid.world/api/payments/stripe (checkout.session.completed, checkout.session.async_payment_succeeded)

Stripe requires both its secret key and endpoint signing secret; Paystack verifies HMAC-SHA512 with its secret key. Matching order reference, currency and amount are required. Stripe also matches its saved session ID. Signed callbacks update pending orders idempotently. Browser return URLs never mark an order paid. If a callback is delayed, refresh the order list; retry the event in the provider dashboard if necessary. Rotating credentials may interrupt callbacks for pending checkouts. Provider merchant approval, supported currency and transaction fees apply. No real payment has been performed during development.

The current marketplace is single-merchant settlement through the operator’s configured gateway account. Tenant sellers list offers, the operator approves publication and handles seller settlement/refunds manually. There is no escrow, automated split payout, tax engine, subscription billing or automated refund API. Listing descriptions must state fulfillment/refund terms; orders capture an immutable name/amount/currency snapshot.

## Legal completion

Terms, privacy and copyright name Olamide Olatayo Bello Corporation. Privacy/copyright/refund requests are stored and visible to super admins; resolving a request records completion but does not erase data automatically. Operator must supply a public business/legal contact, jurisdiction-specific requirements and documented retention/backup policy before broad public launch. Have qualified counsel review the supplied terms for the actual business and jurisdictions; no invented registration address or legal compliance claim is included. Third-party libraries, trademarks and user content retain their respective ownership/licenses.


## Kakakin publication across two hosts

Kakakin runs on 154.16.170.86. Public africanappsstore.space currently points to 181.214.149.146. Updating an africanappsstore.service copy on the Kakakin machine does not update that public store. The Kakakin publisher now checks all public DNS addresses against the target host before it changes store files. It does not move DNS or replace other domains. For verified NAT deployments, Ansible may be given store_public_addresses explicitly.

On the public store host (181.214.149.146), run:

```sh
curl -fL https://raw.githubusercontent.com/olamidebello/africanappsstore/main/scripts/publish-kakakin.sh -o /root/publish-kakakin.sh
bash /root/publish-kakakin.sh
```

The bootstrap preserves source edits, updates the existing store with database/code backups, checks the locally served APK checksum and catalog entry, then verifies public HTTPS downloads and catalog. No Kakakin application rebuild or administrator password is needed. From a controller already authorized for SSH to the store, use `ansible-playbook -i '181.214.149.146,' -u root ansible/publish-mobile.yml` in the Kakakin checkout instead. SSH authorization must already exist; the script does not copy credentials or change DNS to work around missing access.

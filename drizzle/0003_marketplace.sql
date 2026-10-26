CREATE TABLE products (id TEXT PRIMARY KEY,tenant TEXT NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',created TEXT NOT NULL);
--> statement-breakpoint
CREATE INDEX products_tenant ON products(tenant,status);
--> statement-breakpoint
CREATE TABLE orders (id TEXT PRIMARY KEY,tenant TEXT NOT NULL,buyer TEXT NOT NULL,email TEXT NOT NULL,product TEXT NOT NULL,name TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,provider TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',provider_id TEXT,checkout_url TEXT,fulfillment TEXT NOT NULL DEFAULT 'unfulfilled',terms_version TEXT NOT NULL DEFAULT '2026-10-26',created TEXT NOT NULL);
--> statement-breakpoint
CREATE INDEX orders_buyer ON orders(buyer,created);
--> statement-breakpoint
CREATE TABLE legal_requests (id TEXT PRIMARY KEY,user TEXT NOT NULL,email TEXT NOT NULL,kind TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created TEXT NOT NULL);

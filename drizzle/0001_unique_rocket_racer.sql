ALTER TABLE `campaigns` ADD `automatic` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX `contacts_tenant_phone` ON `contacts` (`tenant`,`phone`);--> statement-breakpoint
CREATE INDEX `delivery_provider` ON `deliveries` (`provider_id`);--> statement-breakpoint
CREATE INDEX `delivery_tenant_contact` ON `deliveries` (`tenant`,`contact`);--> statement-breakpoint
CREATE UNIQUE INDEX `members_tenant_email` ON `members` (`tenant`,`email`);
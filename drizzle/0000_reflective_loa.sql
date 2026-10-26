CREATE TABLE `campaigns` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`name` text NOT NULL,
	`channel` text NOT NULL,
	`message` text NOT NULL,
	`segment` text DEFAULT 'All contacts' NOT NULL,
	`status` text DEFAULT 'draft' NOT NULL,
	`mode` text DEFAULT 'sandbox' NOT NULL,
	`scheduled` text,
	`template` text,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `contacts` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`name` text NOT NULL,
	`phone` text NOT NULL,
	`email` text DEFAULT '' NOT NULL,
	`segment` text DEFAULT 'General' NOT NULL,
	`consent` integer DEFAULT 0 NOT NULL,
	`consent_source` text DEFAULT '' NOT NULL,
	`consent_at` text,
	`channel` text DEFAULT 'Both' NOT NULL,
	`status` text DEFAULT 'active' NOT NULL,
	`test` integer DEFAULT 0 NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `deliveries` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`campaign` text NOT NULL,
	`contact` text NOT NULL,
	`status` text NOT NULL,
	`provider_id` text,
	`error` text,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `events` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`actor` text NOT NULL,
	`action` text NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `members` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`email` text NOT NULL,
	`role` text DEFAULT 'viewer' NOT NULL
);
--> statement-breakpoint
CREATE TABLE `referrals` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`name` text NOT NULL,
	`message` text NOT NULL,
	`url` text NOT NULL,
	`visits` integer DEFAULT 0 NOT NULL,
	`signups` integer DEFAULT 0 NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `settings` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`value` text DEFAULT '{}' NOT NULL
);
--> statement-breakpoint
CREATE TABLE `templates` (
	`id` text PRIMARY KEY NOT NULL,
	`tenant` text NOT NULL,
	`name` text NOT NULL,
	`channel` text NOT NULL,
	`body` text NOT NULL,
	`provider_name` text,
	`language` text DEFAULT 'en_US' NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `tenants` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`status` text DEFAULT 'active' NOT NULL,
	`plan` text DEFAULT 'Starter' NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`email` text NOT NULL,
	`name` text NOT NULL,
	`role` text DEFAULT 'member' NOT NULL,
	`status` text DEFAULT 'active' NOT NULL,
	`created` text NOT NULL
);

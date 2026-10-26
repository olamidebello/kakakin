CREATE TABLE `dispatch_locks` (
	`tenant` text PRIMARY KEY NOT NULL,
	`token` text NOT NULL,
	`created` text NOT NULL
);

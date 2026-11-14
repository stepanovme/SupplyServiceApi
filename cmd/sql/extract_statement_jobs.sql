-- База данных: `supply_service`

CREATE TABLE `extract_statement_jobs` (
  `id` char(36) NOT NULL,
  `settings_api_bank_id` char(36) NOT NULL,
  `account_number` varchar(50) NOT NULL,
  `statement_date_from` date NOT NULL,
  `statement_date_to` date NOT NULL,
  `status` enum('pending','running','completed','failed') NOT NULL DEFAULT 'pending',
  `days_requested` int NOT NULL DEFAULT 0,
  `days_processed` int NOT NULL DEFAULT 0,
  `days_succeeded` int NOT NULL DEFAULT 0,
  `days_failed` int NOT NULL DEFAULT 0,
  `current_date_processing` date DEFAULT NULL,
  `fetched` int NOT NULL DEFAULT 0,
  `created_count` int NOT NULL DEFAULT 0,
  `skipped_duplicates` int NOT NULL DEFAULT 0,
  `errors` json DEFAULT NULL,
  `error_message` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `created_by` char(36) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `extract_statement_jobs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `settings_api_bank_id` (`settings_api_bank_id`),
  ADD KEY `status` (`status`),
  ADD KEY `created_by` (`created_by`);

ALTER TABLE `extract_statement_jobs`
  ADD CONSTRAINT `extract_statement_jobs_bank_fk` FOREIGN KEY (`settings_api_bank_id`) REFERENCES `settings_api_bank` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `extract_statement_jobs_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

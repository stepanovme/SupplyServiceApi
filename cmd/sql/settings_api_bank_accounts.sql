-- База данных: `supply_service`

CREATE TABLE `settings_api_bank_accounts` (
  `id` char(36) NOT NULL,
  `settings_api_bank_id` char(36) NOT NULL,
  `account_number` varchar(50) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `currency` varchar(10) NOT NULL DEFAULT 'RUB',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  `created_by` char(36) NOT NULL,
  `updated_by` char(36) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `settings_api_bank_accounts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `settings_api_bank_id` (`settings_api_bank_id`),
  ADD KEY `created_by` (`created_by`),
  ADD KEY `updated_by` (`updated_by`);

ALTER TABLE `settings_api_bank_accounts`
  ADD CONSTRAINT `settings_api_bank_accounts_bank_fk` FOREIGN KEY (`settings_api_bank_id`) REFERENCES `settings_api_bank` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `settings_api_bank_accounts_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `settings_api_bank_accounts_updated_by_fk` FOREIGN KEY (`updated_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

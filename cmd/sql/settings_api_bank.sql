-- База данных: `supply_service`

CREATE TABLE `settings_api_bank` (
  `id` char(36) NOT NULL,
  `name` varchar(255) NOT NULL,
  `bank_type` varchar(50) NOT NULL,
  `config` json NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  `created_by` char(36) NOT NULL,
  `updated_by` char(36) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `settings_api_bank`
  ADD PRIMARY KEY (`id`),
  ADD KEY `bank_type` (`bank_type`),
  ADD KEY `created_by` (`created_by`),
  ADD KEY `updated_by` (`updated_by`);

ALTER TABLE `settings_api_bank`
  ADD CONSTRAINT `settings_api_bank_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `settings_api_bank_updated_by_fk` FOREIGN KEY (`updated_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

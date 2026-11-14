-- База данных: `supply_service`

CREATE TABLE `business_cards` (
  `id` char(36) NOT NULL,
  `settings_api_bank_id` char(36) DEFAULT NULL,
  `bank_business_card_id` varchar(64) DEFAULT NULL,
  `source` enum('manual','sberbank') NOT NULL DEFAULT 'manual',
  `bank_type` enum('sberbank','alfabank','tbank') DEFAULT NULL,
  `account_number` varchar(50) DEFAULT NULL,
  `card_number_mask` varchar(32) DEFAULT NULL,
  `card_last4` varchar(4) DEFAULT NULL,
  `embossed_name` varchar(255) DEFAULT NULL,
  `holder_name` varchar(255) DEFAULT NULL,
  `holder_user_id` char(36) DEFAULT NULL,
  `card_open_date` date DEFAULT NULL,
  `expiry_date` date DEFAULT NULL,
  `card_status` varchar(20) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  `created_by` char(36) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `business_cards`
  ADD PRIMARY KEY (`id`),
  ADD KEY `settings_api_bank_id` (`settings_api_bank_id`),
  ADD KEY `card_last4` (`card_last4`),
  ADD KEY `holder_user_id` (`holder_user_id`),
  ADD KEY `created_by` (`created_by`),
  ADD UNIQUE KEY `uq_business_cards_bank_card` (`settings_api_bank_id`, `bank_business_card_id`);

ALTER TABLE `business_cards`
  ADD CONSTRAINT `business_cards_bank_fk` FOREIGN KEY (`settings_api_bank_id`) REFERENCES `settings_api_bank` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `business_cards_holder_user_fk` FOREIGN KEY (`holder_user_id`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `business_cards_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

-- --------------------------------------------------------

CREATE TABLE `extract_business_cards` (
  `id` char(36) NOT NULL,
  `extract_id` varchar(36) NOT NULL,
  `business_card_id` char(36) NOT NULL,
  `object_id` char(36) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` char(36) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `extract_business_cards`
  ADD PRIMARY KEY (`id`),
  ADD KEY `extract_id` (`extract_id`),
  ADD KEY `business_card_id` (`business_card_id`),
  ADD KEY `object_id` (`object_id`),
  ADD KEY `created_by` (`created_by`);

ALTER TABLE `extract_business_cards`
  ADD CONSTRAINT `extract_business_cards_card_fk` FOREIGN KEY (`business_card_id`) REFERENCES `business_cards` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `extract_business_cards_object_fk` FOREIGN KEY (`object_id`) REFERENCES `{{REFERENCE_DB_NAME}}`.`objects` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `extract_business_cards_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

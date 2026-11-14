-- База данных: `supply_service`
-- Расценки подрядчиков по смете: цена для подрядчика на работу сметы (за единицу работы), статус утверждения,
-- связь с договором из реестра договоров (contracts)
CREATE TABLE `estimate_contractor_rates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `estimate_id` int NOT NULL,
  `contractor_id` char(36) NOT NULL,
  `contract_id` int DEFAULT NULL,
  `status` enum('pending','approved') NOT NULL DEFAULT 'pending',
  `comment` varchar(500) DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `approved_by` char(36) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `estimate_contractor` (`estimate_id`,`contractor_id`),
  KEY `contractor_id` (`contractor_id`),
  KEY `contract_id` (`contract_id`),
  CONSTRAINT `estimate_contractor_rates_fk` FOREIGN KEY (`estimate_id`) REFERENCES `estimates` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_contractor_rate_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `rate_id` int NOT NULL,
  `work_id` int NOT NULL,
  `unit_price` decimal(18,2) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `rate_work` (`rate_id`,`work_id`),
  KEY `work_id` (`work_id`),
  CONSTRAINT `estimate_contractor_rate_items_rate_fk` FOREIGN KEY (`rate_id`) REFERENCES `estimate_contractor_rates` (`id`) ON DELETE CASCADE,
  CONSTRAINT `estimate_contractor_rate_items_work_fk` FOREIGN KEY (`work_id`) REFERENCES `estimate_works` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

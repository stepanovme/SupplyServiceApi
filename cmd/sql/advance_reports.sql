-- База данных: `supply_service`
-- Авансовые отчёты: набор чеков, который можно отправить в 1С (черновик «Авансового отчёта»).

-- Тестовые профили 1С: только в них при отправке разрешено автоматически создавать номенклатуру и контрагентов
ALTER TABLE `1c_profiles` ADD COLUMN `is_test` tinyint(1) NOT NULL DEFAULT 0;
UPDATE `1c_profiles` SET `is_test` = 1 WHERE `name` = 'Тестовая база' AND `api_link` LIKE '%4259905%';

CREATE TABLE `advance_reports` (
  `id` char(36) NOT NULL,
  `number` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) DEFAULT NULL,
  `report_date` date NOT NULL,
  `comment` text DEFAULT NULL,
  `person_user_id` varchar(36) DEFAULT NULL,
  -- draft - собран у нас, в 1С не отправлялся (или отправка не удалась); sent - создан в 1С
  `status` enum('draft','sent') NOT NULL DEFAULT 'draft',
  `total_sum` decimal(14,2) NOT NULL DEFAULT 0,
  `one_c_profile_id` int DEFAULT NULL,
  `one_c_organization_ref_key` char(36) DEFAULT NULL,
  `one_c_organization_name` varchar(300) DEFAULT NULL,
  `one_c_person_ref_key` char(36) DEFAULT NULL,
  `one_c_person_name` varchar(300) DEFAULT NULL,
  `one_c_ref_key` char(36) DEFAULT NULL,
  `one_c_number` varchar(50) DEFAULT NULL,
  `one_c_sent_at` datetime DEFAULT NULL,
  `one_c_sent_by` varchar(36) DEFAULT NULL,
  `one_c_error` text DEFAULT NULL,
  `created_by` varchar(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_advance_reports_number` (`number`),
  KEY `created_by` (`created_by`),
  KEY `status` (`status`),
  KEY `report_date` (`report_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Чек входит максимум в один авансовый отчёт (UNIQUE receipt_id) - иначе он попал бы в 1С дважды
CREATE TABLE `advance_report_receipts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `report_id` char(36) NOT NULL,
  `receipt_id` char(36) NOT NULL,
  `added_by` varchar(36) NOT NULL,
  `added_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_advance_report_receipts_receipt` (`receipt_id`),
  KEY `report_id` (`report_id`),
  CONSTRAINT `advance_report_receipts_report_fk` FOREIGN KEY (`report_id`) REFERENCES `advance_reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `advance_report_receipts_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

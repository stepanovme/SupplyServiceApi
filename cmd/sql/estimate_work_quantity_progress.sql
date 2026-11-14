-- База данных: `supply_service`
-- Работы сметы и справочника имеют единицу измерения и количество (объём);
-- факт выполнения работ сметы ("Стройка - работы"): сколько и когда сделано
ALTER TABLE `estimate_works`
  ADD COLUMN `unit_name` varchar(50) DEFAULT NULL,
  ADD COLUMN `quantity` decimal(18,4) NOT NULL DEFAULT 0;

ALTER TABLE `price_work_items`
  ADD COLUMN `unit_name` varchar(50) DEFAULT NULL,
  ADD COLUMN `quantity` decimal(18,4) NOT NULL DEFAULT 0;

CREATE TABLE `estimate_work_progress` (
  `id` int NOT NULL AUTO_INCREMENT,
  `work_id` int NOT NULL,
  `date` date NOT NULL,
  `quantity` decimal(18,4) NOT NULL,
  `comment` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `work_id` (`work_id`,`date`),
  CONSTRAINT `estimate_work_progress_fk` FOREIGN KEY (`work_id`) REFERENCES `estimate_works` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

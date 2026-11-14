-- База данных: `supply_service`
-- Справочник работ: у работы нет своей единицы и цены, она состоит из ресурсов
ALTER TABLE `price_work_items` DROP COLUMN `unit_name`, DROP COLUMN `price`;

CREATE TABLE `price_work_item_resources` (
  `id` int NOT NULL AUTO_INCREMENT,
  `item_id` int NOT NULL,
  `position` int NOT NULL,
  `type` enum('material','machine','overhead','labor','profit') NOT NULL,
  `name` varchar(255) NOT NULL,
  `contractor_id` char(36) DEFAULT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit_name` varchar(50) DEFAULT NULL,
  `unit_price` decimal(18,2) NOT NULL DEFAULT 0,
  `markup_percent` decimal(9,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `item_id` (`item_id`,`position`),
  CONSTRAINT `price_work_item_resources_fk` FOREIGN KEY (`item_id`) REFERENCES `price_work_items` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

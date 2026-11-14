-- База данных: `supply_service`
-- Стороны сметы (заказчик, инвестор, подрядчик) и акты закрытия объёмов по смете
-- (с заказчиком / с подрядчиком)
ALTER TABLE `estimates`
  ADD COLUMN `customer_id` char(36) DEFAULT NULL,
  ADD COLUMN `investor_id` char(36) DEFAULT NULL,
  ADD COLUMN `contractor_id` char(36) DEFAULT NULL;

CREATE TABLE `estimate_acts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `estimate_id` int NOT NULL,
  `kind` enum('customer','contractor') NOT NULL,
  `counterparty_id` char(36) NOT NULL,
  `number` int NOT NULL,
  `date` date NOT NULL,
  `date_from` date NOT NULL,
  `date_to` date NOT NULL,
  `status` enum('unsigned','signed') NOT NULL DEFAULT 'unsigned',
  `signed_at` datetime DEFAULT NULL,
  `signed_by` char(36) DEFAULT NULL,
  `comment` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `created_by` char(36) NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `updated_by` char(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `act_number` (`estimate_id`,`kind`,`counterparty_id`,`number`),
  KEY `counterparty_id` (`counterparty_id`),
  CONSTRAINT `estimate_acts_fk` FOREIGN KEY (`estimate_id`) REFERENCES `estimates` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `estimate_act_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `act_id` int NOT NULL,
  `work_id` int NOT NULL,
  `quantity` decimal(18,4) NOT NULL,
  `unit_price` decimal(18,2) NOT NULL,
  `customer_price` decimal(18,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `act_work` (`act_id`,`work_id`),
  KEY `work_id` (`work_id`),
  CONSTRAINT `estimate_act_items_act_fk` FOREIGN KEY (`act_id`) REFERENCES `estimate_acts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `estimate_act_items_work_fk` FOREIGN KEY (`work_id`) REFERENCES `estimate_works` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- База данных: `supply_service`
-- Кассовые чеки: добавляются вручную, по QR-коду или по фото (данные чека берутся с proverkacheka.com).

CREATE TABLE `purchase_receipts` (
  `id` char(36) NOT NULL,
  `created_by` varchar(36) NOT NULL,
  `source` enum('manual','qr','photo') NOT NULL DEFAULT 'manual',
  `object_id` char(36) DEFAULT NULL,
  `business_card_id` char(36) DEFAULT NULL,
  `fn` varchar(32) DEFAULT NULL,
  `fd` varchar(20) DEFAULT NULL,
  `fp` varchar(20) DEFAULT NULL,
  `receipt_type` tinyint NOT NULL DEFAULT 1,
  `purchased_at` datetime DEFAULT NULL,
  `total_sum` decimal(14,2) NOT NULL,
  `cash_sum` decimal(14,2) DEFAULT NULL,
  `ecash_sum` decimal(14,2) DEFAULT NULL,
  `seller_name` varchar(500) DEFAULT NULL,
  `seller_inn` varchar(12) DEFAULT NULL,
  `retail_place` varchar(500) DEFAULT NULL,
  `retail_place_address` varchar(1000) DEFAULT NULL,
  `qr_raw` text DEFAULT NULL,
  `comment` text DEFAULT NULL,
  `raw_data` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  -- один и тот же фискальный чек нельзя завести дважды (у ручных чеков fn/fd/fp пустые - NULL не конфликтуют)
  UNIQUE KEY `uq_purchase_receipts_fiscal` (`fn`,`fd`,`fp`),
  KEY `created_by` (`created_by`),
  KEY `object_id` (`object_id`),
  KEY `business_card_id` (`business_card_id`),
  KEY `purchased_at` (`purchased_at`),
  CONSTRAINT `purchase_receipts_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `purchase_receipts_business_card_fk` FOREIGN KEY (`business_card_id`) REFERENCES `business_cards` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `purchase_receipt_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `receipt_id` char(36) NOT NULL,
  `position` int NOT NULL,
  `name` varchar(500) NOT NULL,
  `price` decimal(14,2) NOT NULL,
  `quantity` decimal(14,3) NOT NULL,
  `sum` decimal(14,2) NOT NULL,
  `nds_code` int DEFAULT NULL,
  `nds_sum` decimal(14,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `receipt_id` (`receipt_id`),
  CONSTRAINT `purchase_receipt_items_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Товарные категории чека (справочник warehouse_category); у чека их может быть несколько
CREATE TABLE `purchase_receipt_categories` (
  `receipt_id` char(36) NOT NULL,
  `category_id` char(36) NOT NULL,
  PRIMARY KEY (`receipt_id`,`category_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `purchase_receipt_categories_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `purchase_receipt_categories_category_fk` FOREIGN KEY (`category_id`) REFERENCES `warehouse_category` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Доступ к чеку для других пользователей (владелец - created_by - имеет полный доступ всегда)
CREATE TABLE `purchase_receipt_access` (
  `id` int NOT NULL AUTO_INCREMENT,
  `receipt_id` char(36) NOT NULL,
  `user_id` varchar(36) NOT NULL,
  `access_level` enum('view','edit') NOT NULL DEFAULT 'view',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` varchar(36) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_purchase_receipt_access` (`receipt_id`,`user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `purchase_receipt_access_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `purchase_receipt_access_user_fk` FOREIGN KEY (`user_id`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

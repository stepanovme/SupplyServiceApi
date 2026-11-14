-- База данных: `supply_service`
-- Дополнения к чекам: от кого / для кого, способ оплаты, хештеги, комментарии.

ALTER TABLE `purchase_receipts`
  ADD COLUMN `from_user_id` varchar(36) DEFAULT NULL,
  ADD COLUMN `for_user_id` varchar(36) DEFAULT NULL,
  -- business_card - оплачено бизнес-картой (при этом задан business_card_id), cash - наличные,
  -- credit_card - кредитная карта (без уточнения какая)
  ADD COLUMN `payment_method` enum('business_card','cash','credit_card') DEFAULT NULL,
  ADD KEY `from_user_id` (`from_user_id`),
  ADD KEY `for_user_id` (`for_user_id`),
  ADD KEY `payment_method` (`payment_method`),
  ADD KEY `created_at` (`created_at`),
  ADD CONSTRAINT `purchase_receipts_from_user_fk` FOREIGN KEY (`from_user_id`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `purchase_receipts_for_user_fk` FOREIGN KEY (`for_user_id`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

-- у уже существующих чеков с бизнес-картой способ оплаты - бизнес-карта
UPDATE `purchase_receipts` SET `payment_method` = 'business_card' WHERE `business_card_id` IS NOT NULL AND `payment_method` IS NULL;

-- Хештеги чека (любое количество, нижний регистр, без «#»)
CREATE TABLE `purchase_receipt_hashtags` (
  `receipt_id` char(36) NOT NULL,
  `tag` varchar(50) NOT NULL,
  PRIMARY KEY (`receipt_id`,`tag`),
  KEY `tag` (`tag`),
  CONSTRAINT `purchase_receipt_hashtags_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Комментарии к чеку (переписка тех, у кого есть доступ к чеку)
CREATE TABLE `purchase_receipt_comments` (
  `id` char(36) NOT NULL,
  `receipt_id` char(36) NOT NULL,
  `user_id` varchar(36) NOT NULL,
  `text` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `receipt_id` (`receipt_id`,`created_at`),
  CONSTRAINT `purchase_receipt_comments_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

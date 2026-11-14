-- База данных: `supply_service`
-- Логотипы продавцов чеков по ИНН. Логотип - либо ссылка на внешнюю картинку (logo_url),
-- либо загруженный файл (storage_name, лежит в SUPPLY_RECEIPT_LOGOS_DIR); один из двух.
CREATE TABLE `receipt_seller_logos` (
  `id` char(36) NOT NULL,
  `seller_inn` varchar(12) NOT NULL,
  `seller_name` varchar(255) DEFAULT NULL,
  `logo_url` varchar(1000) DEFAULT NULL,
  `storage_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL,
  `created_by` varchar(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_receipt_seller_logos_inn` (`seller_inn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

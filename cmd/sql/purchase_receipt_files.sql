-- База данных: `supply_service`

-- Фотографии/сканы чека; у одного чека их может быть несколько.
-- Сами файлы лежат на диске в SUPPLY_RECEIPT_FILES_DIR/<receipt_id>/<storage_name>.
-- source: upload - загружено вручную, receipt_photo - фото, по которому чек был добавлен.
CREATE TABLE `purchase_receipt_files` (
  `id` char(36) NOT NULL,
  `receipt_id` char(36) NOT NULL,
  `original_name` varchar(255) NOT NULL,
  `storage_name` varchar(100) NOT NULL,
  `mime_type` varchar(100) NOT NULL,
  `file_size` int NOT NULL,
  `md5_hash` char(32) NOT NULL,
  `source` enum('upload','receipt_photo') NOT NULL DEFAULT 'upload',
  `uploaded_by` varchar(36) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `receipt_id` (`receipt_id`),
  CONSTRAINT `purchase_receipt_files_receipt_fk` FOREIGN KEY (`receipt_id`) REFERENCES `purchase_receipts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

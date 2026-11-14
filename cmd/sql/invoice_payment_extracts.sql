-- База данных: `supply_service`
-- Связь «платёж по счёту (invoice_payment) <-> строка выписки (extract_items)».
-- Одна строка выписки может быть привязана к нескольким платежам; уникальна пара (extract_id, invoice_payment_id),
-- см. extract_object_and_multi_invoice_links.sql.

CREATE TABLE `invoice_payment_extracts` (
  `id` char(36) NOT NULL,
  `invoice_payment_id` varchar(36) NOT NULL,
  `extract_id` varchar(36) NOT NULL,
  `scenario` varchar(20) NOT NULL,
  `amount` double(17,2) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` varchar(36) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `invoice_payment_extracts`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_invoice_payment_extracts_pair` (`extract_id`, `invoice_payment_id`),
  ADD KEY `invoice_payment_id` (`invoice_payment_id`),
  ADD KEY `created_by` (`created_by`);

ALTER TABLE `invoice_payment_extracts`
  ADD CONSTRAINT `invoice_payment_extracts_payment_fk` FOREIGN KEY (`invoice_payment_id`) REFERENCES `invoice_payment` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `invoice_payment_extracts_extract_fk` FOREIGN KEY (`extract_id`) REFERENCES `extract_items` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `invoice_payment_extracts_created_by_fk` FOREIGN KEY (`created_by`) REFERENCES `{{DB_NAME}}`.`users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

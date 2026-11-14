-- База данных: `supply_service`
-- 1) Любая строка выписки может быть привязана к объекту (reference_service.objects.id).
ALTER TABLE `extract_items`
  ADD COLUMN `object_id` char(36) DEFAULT NULL,
  ADD KEY `object_id` (`object_id`);

-- 2) Одна строка выписки может быть привязана к нескольким платежам по счетам:
--    уникальна пара (extract_id, invoice_payment_id); amount — доля строки выписки в этом платеже.
ALTER TABLE `invoice_payment_extracts`
  ADD UNIQUE KEY `uq_invoice_payment_extracts_pair` (`extract_id`, `invoice_payment_id`),
  DROP INDEX `uq_invoice_payment_extracts_extract`;

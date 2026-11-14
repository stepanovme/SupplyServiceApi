-- База данных: `supply_service`
-- Счёт: маркер «Акты/УПД не требуются»
ALTER TABLE `invoice`
  ADD COLUMN `closing_docs_not_required` tinyint(1) NOT NULL DEFAULT 0,
  ADD COLUMN `closing_docs_not_required_at` datetime DEFAULT NULL,
  ADD COLUMN `closing_docs_not_required_by` char(36) DEFAULT NULL;

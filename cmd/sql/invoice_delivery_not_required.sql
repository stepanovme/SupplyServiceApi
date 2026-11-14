-- База данных: `supply_service`
-- Счёт: маркер «Доставка не требуется»
ALTER TABLE `invoice`
  ADD COLUMN `delivery_not_required` tinyint(1) NOT NULL DEFAULT 0,
  ADD COLUMN `delivery_not_required_at` datetime DEFAULT NULL,
  ADD COLUMN `delivery_not_required_by` char(36) DEFAULT NULL;

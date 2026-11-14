-- База данных: `supply_service`
-- Заказчик и подрядчик у документов из списка документов (documents_list); контрагенты из reference_service.counterparties.
ALTER TABLE `documents_list`
  ADD COLUMN `customer_id` char(36) DEFAULT NULL,
  ADD COLUMN `contractor_id` char(36) DEFAULT NULL,
  ADD KEY `customer_id` (`customer_id`),
  ADD KEY `contractor_id` (`contractor_id`);

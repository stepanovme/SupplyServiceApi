-- База данных: `supply_service`
-- Реквизиты получателя платежа в счёте (необязательные). Заполняются вручную или при распознавании счёта.
ALTER TABLE `invoice`
  ADD COLUMN `recipient_inn` varchar(12) DEFAULT NULL,
  ADD COLUMN `recipient_kpp` varchar(9) DEFAULT NULL,
  ADD COLUMN `recipient_bank_name` varchar(255) DEFAULT NULL,
  ADD COLUMN `recipient_account` varchar(20) DEFAULT NULL,       -- расчётный счёт (Р/С)
  ADD COLUMN `recipient_corr_account` varchar(20) DEFAULT NULL,  -- корреспондентский счёт (К/С)
  ADD COLUMN `recipient_bik` varchar(9) DEFAULT NULL,
  ADD COLUMN `payment_purpose` text DEFAULT NULL;

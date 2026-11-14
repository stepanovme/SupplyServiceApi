-- phpMyAdmin SQL Dump
-- version 5.2.1deb3
-- https://www.phpmyadmin.net/
--
-- Хост: localhost:3306
-- Время создания: Сен 27 2026 г., 19:56
-- Версия сервера: 8.0.46-0ubuntu0.24.04.4
-- Версия PHP: 8.3.6

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- База данных: `supply_service`
--

-- --------------------------------------------------------

--
-- Структура таблицы `extract_items`
--

CREATE TABLE `extract_items` (
  `id` varchar(36) NOT NULL,
  `operationDate` datetime DEFAULT NULL,
  `amount` double(17,2) DEFAULT NULL,
  `direction` text,
  `paymentPurpose` text,
  `payeeInn` text,
  `payeeKpp` text,
  `payeeName` text,
  `payerInn` text,
  `payerKpp` text,
  `payerName` text,
  `payeeBankName` text,
  `payeeAccount` text,
  `account_number` varchar(50) DEFAULT NULL,
  `bank_type` varchar(20) DEFAULT NULL,
  `external_id` varchar(100) DEFAULT NULL,
  `payee_id` varchar(36) DEFAULT NULL,
  `payer_id` varchar(36) DEFAULT NULL,
  `object_id` char(36) DEFAULT NULL,
  `created_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Индексы сохранённых таблиц
--

--
-- Индексы таблицы `extract_items`
--
ALTER TABLE `extract_items`
  ADD PRIMARY KEY (`id`),
  ADD KEY `payee_id` (`payee_id`),
  ADD KEY `payer_id` (`payer_id`),
  ADD KEY `object_id` (`object_id`),
  ADD KEY `idx_extract_items_account_number` (`account_number`),
  ADD KEY `idx_extract_items_bank_type` (`bank_type`),
  ADD KEY `idx_extract_items_external_id` (`bank_type`, `external_id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

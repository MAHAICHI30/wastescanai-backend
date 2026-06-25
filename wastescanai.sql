-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jun 22, 2026 at 04:25 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `wastescanaidb`
--

-- --------------------------------------------------------

--
-- Table structure for table `admins`
--

CREATE TABLE `admins` (
  `id` int(11) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `admins`
--

INSERT INTO `admins` (`id`, `username`, `password`, `created_at`) VALUES
(1, 'admin', '$2y$10$NImiUbwBZSyogUzo0fYu..iGv3pCtpBgjbyGAHe6IDDoBPFZUfrca', '2026-05-24 15:02:36');

-- --------------------------------------------------------

--
-- Table structure for table `recycle_bins`
--

CREATE TABLE `recycle_bins` (
  `id` int(11) NOT NULL,
  `bin_name` varchar(50) NOT NULL,
  `current_volume` int(11) DEFAULT 0,
  `max_capacity` int(11) DEFAULT 100,
  `last_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `status` varchar(50) DEFAULT 'Normal'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `recycle_bins`
--

INSERT INTO `recycle_bins` (`id`, `bin_name`, `current_volume`, `max_capacity`, `last_updated`, `status`) VALUES
(1, 'plastic', 88, 100, '2026-06-14 09:16:30', 'Normal'),
(2, 'paper', 42, 100, '2026-06-14 09:11:36', 'Normal'),
(3, 'aluminum', 3, 100, '2026-06-11 16:53:27', 'Normal');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(255) DEFAULT NULL,
  `google_id` varchar(100) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `last_active` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `username`, `email`, `password`, `google_id`, `created_at`, `last_active`) VALUES
(1, 'john', 'john@gamil.com', '$2y$10$c/tPk2nKiByQWvm39dwyjuhP/vLQcSmBol4XdXIIR1ixQN4mwCBRy', NULL, '2026-05-24 06:44:48', '2026-06-09 13:02:13'),
(2, 'TAN XIAO MING', 'xiaoming@gmail.com', '$2y$10$B0CjnleOB1aKo25jzUfxk.IzuxZehfRf.Har6yrZdUgmSLYJtC5JG', NULL, '2026-05-24 08:26:24', NULL),
(3, 'Ng Xiao LI', 'xiaoli00@gmail.com', '$2y$10$4cyC//EgJkvjj/5V2SeKrejqrh3o.3OabIB8M8DIPmQXg3GGXnsAW', NULL, '2026-05-24 10:20:58', NULL),
(4, 'abu', 'abu@google.com', '$2y$10$/hsnwwSPTlR3sg1NG42st.QM8Hd.VFE399ko6orMCCtSY7DSbBlyy', NULL, '2026-05-24 10:32:53', NULL),
(5, 'Muthu', 'muthu@gamil.com', '$2y$10$OswUX5.Mk.csu3NTmu.KtOOT4aELqmwwJgJtIJq1nI3fOsCD1nngW', NULL, '2026-05-24 12:15:04', NULL),
(6, 'ai chi', 'mac03@gmail.com', '$2y$10$M.O/F5BRdJICcm.uyXBUYOBPe6K9b.J2.mfwaqH6rxqq49Ag7Q0Fy', NULL, '2026-05-24 16:34:01', NULL),
(7, 'MAH AI CHI', 'aichimah03@gmail.com', NULL, '111334459044680887468', '2026-05-25 10:14:08', '2026-06-22 14:40:41'),
(8, 'Ali', 'aliby@gmail.com', '$2y$10$oNgUHHIjITLkscW0edM2M.l26SnLCUWIYBaY1AlurnIGDq/FevQ3u', NULL, '2026-06-22 13:50:01', '2026-06-22 21:50:20');

-- --------------------------------------------------------

--
-- Table structure for table `waste_records`
--

CREATE TABLE `waste_records` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `record_type` varchar(20) NOT NULL,
  `material_type` varchar(50) NOT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `waste_records`
--

INSERT INTO `waste_records` (`id`, `username`, `record_type`, `material_type`, `image_path`, `created_at`) VALUES
(1, '', 'upload', 'paper', NULL, '2026-06-04 15:47:49'),
(2, '', 'upload', 'unknown', NULL, '2026-06-04 15:57:50'),
(3, '', 'upload', 'paper', NULL, '2026-06-04 15:58:22'),
(4, '', 'upload', 'plastic', NULL, '2026-06-04 16:04:10'),
(5, '', 'upload', 'aluminum', NULL, '2026-06-04 16:04:43'),
(6, '', 'upload', 'paper', NULL, '2026-06-04 16:05:19'),
(7, '', 'upload', 'plastic', NULL, '2026-06-04 16:25:18'),
(8, '', 'upload', 'paper', NULL, '2026-06-04 16:34:34'),
(9, '', 'scan', 'unknown', NULL, '2026-06-04 16:35:11'),
(10, '', 'scan', 'unknown', NULL, '2026-06-04 16:38:20'),
(11, '', 'scan', 'aluminum', NULL, '2026-06-04 16:40:21'),
(12, '', 'scan', 'unknown', NULL, '2026-06-04 16:53:31'),
(13, '', 'scan', 'aluminum', NULL, '2026-06-04 16:56:59'),
(14, '', 'scan', 'unknown', NULL, '2026-06-04 16:57:17'),
(15, '', 'scan', 'aluminum', NULL, '2026-06-04 17:05:00'),
(16, '', 'scan', 'paper', NULL, '2026-06-08 12:11:13'),
(17, '', 'upload', 'paper', NULL, '2026-06-08 12:11:13'),
(18, '', 'scan', 'paper', NULL, '2026-06-08 12:20:24'),
(19, '', 'upload', 'paper', NULL, '2026-06-08 12:20:24'),
(20, '', 'scan', 'paper', NULL, '2026-06-08 12:20:41'),
(21, '', 'upload', 'paper', NULL, '2026-06-08 12:20:41'),
(22, '', 'scan', 'aluminium', NULL, '2026-06-08 12:41:37'),
(23, '', 'upload', 'aluminum', NULL, '2026-06-08 12:41:37'),
(24, '', 'scan', 'paper', NULL, '2026-06-09 04:46:13'),
(25, '', 'upload', 'paper', NULL, '2026-06-09 04:46:13'),
(26, '', 'scan', 'aluminium', NULL, '2026-06-09 04:47:09'),
(27, '', 'upload', 'aluminum', NULL, '2026-06-09 04:47:09'),
(28, '', 'scan', 'paper', NULL, '2026-06-09 15:04:59'),
(29, '', 'upload', 'paper', NULL, '2026-06-09 15:04:59'),
(30, '', 'scan', 'paper', NULL, '2026-06-09 15:18:58'),
(31, '', 'upload', 'paper', NULL, '2026-06-09 15:18:58'),
(32, '', 'scan', 'paper', NULL, '2026-06-11 16:37:50'),
(33, '', 'upload', 'paper', NULL, '2026-06-11 16:37:50'),
(34, '', 'scan', 'aluminium', NULL, '2026-06-11 16:53:27'),
(35, '', 'upload', 'aluminum', NULL, '2026-06-11 16:53:27'),
(36, '', 'scan', 'paper', NULL, '2026-06-14 08:56:47'),
(37, '', 'upload', 'paper', NULL, '2026-06-14 08:56:47'),
(38, '', 'scan', 'plastic', NULL, '2026-06-14 08:58:33'),
(39, '', 'upload', 'plastic', NULL, '2026-06-14 08:58:33'),
(40, '', 'scan', 'paper', NULL, '2026-06-14 09:02:33'),
(41, '', 'upload', 'paper', 'upload/1781427753_IMG_20260530_174133.jpg', '2026-06-14 09:02:33'),
(42, '', 'upload', 'paper', 'upload/1781428295_IMG_20260530_174133.jpg', '2026-06-14 09:11:36'),
(43, '', 'upload', 'plastic', 'upload/1781428590_IMG_20260530_173830.jpg', '2026-06-14 09:16:30');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admins`
--
ALTER TABLE `admins`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `recycle_bins`
--
ALTER TABLE `recycle_bins`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `google_id` (`google_id`);

--
-- Indexes for table `waste_records`
--
ALTER TABLE `waste_records`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admins`
--
ALTER TABLE `admins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `recycle_bins`
--
ALTER TABLE `recycle_bins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `waste_records`
--
ALTER TABLE `waste_records`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=44;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

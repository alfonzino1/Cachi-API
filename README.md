# 🚀 Cache API

> **FastAPI + Redis Cache + PostgreSQL**  
> Высокопроизводительный REST API для управления заметками с использованием кэширования.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

---

## 📖 Описание

Проект демонстрирует реализацию паттерна **Cache-Aside** (Write-Through).
При получении данных приложение сначала проверяет кэш (**Redis**), и только при отсутствии запроса идёт в базу данных (**PostgreSQL**).

Это позволяет:
⚡ Ускорить время ответа (Read) в разы.
 Снизить нагрузку на основную базу данных.

## 🏗️ Архитектура

Проект состоит из 3 микросервисов, объединенных в Docker Network:

1.  **app** (FastAPI) — Обработка запросов и логика кэширования.
2.  **redis** (Redis 7) — In-memory хранилище для кэша (TTL 60s).
3.  **db** (PostgreSQL 15) — Постоянное хранение данных.

```text
┌──────────────────┐      ┌──────────────────┐
│   FastAPI (App)  │─────▶│   Redis (Cache)  │
────────┬─────────┘      └──────────────────┘
         │
         ▼
┌──────────────────┐
│ PostgreSQL (DB)  │
└──────────────────

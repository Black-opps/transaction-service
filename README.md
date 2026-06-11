# Transaction Service - Canonical Ledger

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Black-opps/transaction-service/releases/tag/v1.0.0)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

## 🎯 Overview

The **Transaction Service** serves as the **canonical ledger** and **source of truth** for all financial transactions in the M-PESA platform. It provides an immutable, auditable record of every transaction processed through the system.

## ✨ Features

- ✅ **Immutable Ledger** - Transactions cannot be modified once recorded
- ✅ **Deduplication** - Prevents duplicate transaction processing
- ✅ **Validation** - Ensures data integrity before storage
- ✅ **Event Publishing** - Real-time transaction events via RabbitMQ
- ✅ **PostgreSQL** - Robust relational database with ACID compliance
- ✅ **RESTful API** - Clean, documented API endpoints
- ✅ **Comprehensive Logging** - Request/response logging and error tracking
- ✅ **Alembic Migrations** - Version-controlled database schema changes

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- RabbitMQ (optional, for events)

### Installation

\\\ash
# Clone the repository
git clone https://github.com/Black-opps/transaction-service.git
cd transaction-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Start the service
python -m uvicorn src.main:app --reload --port 8006
\\\

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/transactions | Create a new transaction |
| GET | /api/v1/transactions/{id} | Get transaction by ID |
| GET | /api/v1/transactions | List all transactions |
| GET | /api/v1/transactions/summary | Get transaction summary |
| PATCH | /api/v1/transactions/{id}/status | Update transaction status |

### Interactive API Documentation
- Swagger UI: http://localhost:8006/docs
- ReDoc: http://localhost:8006/redoc

## 📊 Database Schema

\\\sql
transactions:
  - id (UUID, Primary Key)
  - transaction_id (String, Unique)
  - amount (Decimal)
  - currency (String)
  - transaction_type (String)
  - sender (String)
  - recipient (String)
  - status (String)
  - timestamp (DateTime)
  - metadata (JSONB)
  - created_at (DateTime)
  - updated_at (DateTime)
\\\

## 🐳 Docker

\\\ash
# Build image
docker build -t transaction-service .

# Run container
docker run -p 8006:8006 transaction-service
\\\

## 🔗 Related Services

- [Parser Service](https://github.com/Black-opps/mpesa-transaction-parser) - Feeds transactions to the ledger
- [Categorizer Service](https://github.com/Black-opps/transaction-categorizer) - Adds categories to transactions
- [Analytics Service](https://github.com/Black-opps/mpesa-analytics-api) - Analyzes transaction data
- [Cashflow Analyzer](https://github.com/Black-opps/cashflow-analyzer) - Cash flow intelligence

## 📝 Version History

### v1.0.0 (Current)
- Initial release
- Canonical ledger implementation
- Basic CRUD operations
- Transaction validation
- Alembic migrations

## 📄 License

MIT

## 👤 Author

**Black-opps**
- GitHub: [@Black-opps](https://github.com/Black-opps)

## ⭐ Show Your Support

If this project helped you, please give it a ⭐ on GitHub!

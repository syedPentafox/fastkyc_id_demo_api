# FastAPI MySQL Boilerplate - Quick Setup Guide

## Prerequisites
- Python 3.10+
- MySQL 8.0+
- Poetry (optional, can use pip)

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd fastapitest

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

**Using Poetry (Recommended):**
```bash
poetry install
```

**Using pip:**
```bash
pip install -r requirements.txt
```

### 3. Setup MySQL Database

```bash
# Login to MySQL
mysql -u root -p

# Create database
CREATE DATABASE myapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Create user (optional, for production)
CREATE USER 'myapp_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON myapp.* TO 'myapp_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and update with your settings:

```bash
cp .env.example .env
```

Edit `.env` file:
```env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/myapp
JWT_SECRET_KEY=your-secret-key-here
AES_SECRET_KEY=your-aes-key-here
ALLOWED_ORIGINS=http://localhost:3000
```

### 5. Run the Application

```bash
# Using Python directly
python app.py

# Or using uvicorn
uvicorn app:app --reload --host 127.0.0.1 --port 5000
```

The application will be available at:
- **API**: http://127.0.0.1:5000
- **Swagger Docs**: http://127.0.0.1:5000/docs
- **ReDoc**: http://127.0.0.1:5000/redoc

## Docker Setup (Alternative)

```bash
# Start MySQL and application containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

## Database Migrations with Alembic

### Initialize Alembic (First Time Only)

```bash
alembic init migrations
```

Update `alembic.ini`:
```ini
sqlalchemy.url = mysql+pymysql://root:password@localhost:3306/myapp
```

Update `migrations/env.py`:
```python
from orm_model.core_models import Base
target_metadata = Base.metadata
```

### Create and Apply Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Testing the Setup

1. **Check Health Endpoint:**
   ```bash
   curl http://127.0.0.1:5000/api/health-check
   ```

2. **Access Swagger UI:**
   Open http://127.0.0.1:5000/docs in your browser

3. **Verify Database Tables:**
   ```bash
   mysql -u root -p myapp -e "SHOW TABLES;"
   ```

## Common Issues

### Connection Error
- Verify MySQL is running: `sudo systemctl status mysql` (Linux) or check Services (Windows)
- Check DATABASE_URL in `.env` file
- Ensure MySQL user has proper permissions

### Import Errors
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check Python version: `python --version` (should be 3.10+)

### Port Already in Use
- Change port in `app.py`: `uvicorn.run(app, host="127.0.0.1", port=8000)`
- Or kill process using port 5000

## Next Steps

1. Review the models in `orm_model/core_models.py`
2. Explore the API endpoints in `routers/`
3. Customize authentication in `utils/authentication.py`
4. Add your business logic

## Support

For issues and questions, refer to:
- FastAPI Documentation: https://fastapi.tiangolo.com/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- MySQL Documentation: https://dev.mysql.com/doc/

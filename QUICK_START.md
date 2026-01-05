# FastKYC Application - Quick Start Checklist

## ✅ Pre-Setup
- [ ] MySQL 8.0+ installed and running
- [ ] Python 3.10+ installed
- [ ] SQL dump file available: `fastkyc_dump_1_5 (1).sql`

## ✅ Database Setup
```bash
# 1. Create database
mysql -u root -p
CREATE DATABASE fastkyc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# 2. Import SQL dump
mysql -u root -p fastkyc < "fastkyc_dump_1_5 (1).sql"

# 3. Verify tables
mysql -u root -p fastkyc -e "SHOW TABLES;"
```

## ✅ Application Setup
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
poetry install
# OR: pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

## ✅ Configuration
Edit `.env` file:
```env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/fastkyc
JWT_SECRET_KEY=your-secret-key-here
AES_SECRET_KEY=your-aes-key-here
ALLOWED_ORIGINS=http://localhost:3000
```

## ✅ Run Application
```bash
python app.py
```

## ✅ Validation
- [ ] Health check: http://127.0.0.1:5000/api/health-check
- [ ] Swagger UI: http://127.0.0.1:5000/docs
- [ ] No errors in terminal logs

## 📚 Detailed Guide
See `APPLICATION_SETUP.md` for complete step-by-step instructions.

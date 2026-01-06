# FastKYC Application - Final Setup Steps

## ✅ COMPLETED
- Virtual environment created
- Dependencies installed successfully

---

## NEXT STEPS

### Step 1: Import Your Database

```bash
# Create the database
mysql -u root -p
```

In MySQL prompt, run:
```sql
CREATE DATABASE fastkyc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

Then import your SQL dump:
```bash
mysql -u root -p fastkyc < "fastkyc_dump_1_5 (1).sql"
```

Verify tables were created:
```bash
mysql -u root -p fastkyc -e "SHOW TABLES;"
```
You should see 20 tables.

---

### Step 2: Configure .env File

Make sure your `.env` file has the correct database credentials:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/fastkyc
JWT_SECRET_KEY=your-secret-key-change-this-in-production
AES_SECRET_KEY=your-aes-key-32-characters-minimum
ALLOWED_ORIGINS=http://localhost:3000
ADMIN_CLIENT_ID=admin
ADMIN_CLIENT_KEY=admin
API_URL=http://127.0.0.1:5000
```

---

### Step 3: Run the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run with uvicorn
uvicorn app:app --reload --host 127.0.0.1 --port 5000
```

**Expected output:**
```
>>>>>Connecting to the database
INFO:     Uvicorn running on http://127.0.0.1:5000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

### Step 4: Validate

**1. Health Check:**
```bash
curl http://127.0.0.1:5000/api/health-check
```
Expected: `{"message":"Application running sucessfully"}`

**2. Swagger UI:**
Open in browser: http://127.0.0.1:5000/docs

**3. Check Database:**
```bash
mysql -u root -p fastkyc -e "SELECT COUNT(*) FROM customer1;"
```

---

## Quick Commands

```bash
# Activate venv
source venv/bin/activate

# Run application
uvicorn app:app --reload --host 127.0.0.1 --port 5000

# Stop application
Press CTRL+C

# Deactivate venv
deactivate
```

---

## Troubleshooting

**Connection Error:**
- Check MySQL is running
- Verify DATABASE_URL in `.env`
- Ensure database `fastkyc` exists

**Port in Use:**
- Change port: `uvicorn app:app --reload --host 127.0.0.1 --port 8000`

**Import Error:**
- Make sure venv is activated: `source venv/bin/activate`

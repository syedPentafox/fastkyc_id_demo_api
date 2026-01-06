# FastKYC Application - macOS Setup

## ✅ Step 1: Virtual Environment (DONE)
```bash
python3 -m venv venv
```

## ✅ Step 2: Install Dependencies (IN PROGRESS)
```bash
source venv/bin/activate
pip install -r requirements.txt
```
⏳ **This is currently running... please wait for it to complete**

---

## Step 3: Import Database

```bash
# Create database
mysql -u root -p
```

In MySQL prompt:
```sql
CREATE DATABASE fastkyc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

Then import your dump:
```bash
mysql -u root -p fastkyc < "fastkyc_dump_1_5 (1).sql"
```

---

## Step 4: Configure Environment

Make sure your `.env` file has:
```env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/fastkyc
JWT_SECRET_KEY=your-secret-key-here
AES_SECRET_KEY=your-aes-key-here
ALLOWED_ORIGINS=http://localhost:3000
```

---

## Step 5: Run with Uvicorn

Once dependencies finish installing:

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run with uvicorn directly
uvicorn app:app --reload --host 127.0.0.1 --port 5000
```

**OR** run the app.py file:
```bash
python3 app.py
```

---

## Validation

1. **Health Check:**
   ```bash
   curl http://127.0.0.1:5000/api/health-check
   ```

2. **Swagger UI:**
   Open: http://127.0.0.1:5000/docs

3. **Check Logs:**
   Look for "Application startup complete" in terminal

---

## Important macOS Notes

- ✅ Use `python3` instead of `python`
- ✅ Use `pip3` or `pip` (inside venv)
- ✅ Always activate venv: `source venv/bin/activate`
- ✅ MySQL might be at `/usr/local/mysql/bin/mysql`

---

## Quick Commands

```bash
# Activate venv
source venv/bin/activate

# Run application
uvicorn app:app --reload --host 127.0.0.1 --port 5000

# Stop application
# Press CTRL+C

# Deactivate venv
deactivate
```

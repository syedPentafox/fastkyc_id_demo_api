# FastKYC Application - Complete Setup Guide

## Prerequisites Checklist
- ✅ Python 3.10+ installed
- ✅ MySQL 8.0+ installed and running
- ✅ SQL dump file: `fastkyc_dump_1_5 (1).sql`

---

## Step-by-Step Setup Process

### STEP 1: Create MySQL Database

```bash
# Login to MySQL
mysql -u root -p

# Create a new database for your application
CREATE DATABASE fastkyc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Exit MySQL
EXIT;
```

---

### STEP 2: Import Your Database Schema

```bash
# Import the SQL dump file
mysql -u root -p fastkyc < "fastkyc_dump_1_5 (1).sql"

# Verify tables were created
mysql -u root -p fastkyc -e "SHOW TABLES;"
```

**Expected Output:** You should see 20 tables including:
- api_history
- api_key
- category
- customer1
- customer_bank_details
- features_master
- user_flow_master
- etc.

---

### STEP 3: Install Python Dependencies

```bash
# Create and activate virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies using Poetry
poetry install

# OR using pip
pip install -r requirements.txt
```

---

### STEP 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
# Database Configuration
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/fastkyc

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
ACCESS_TOKEN_EXPIRE_HOURS=24
REFRESH_TOKEN_EXPIRE_HOURS=720

# AES Encryption
AES_SECRET_KEY=your-aes-secret-key-32-chars-min

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# File Storage
LOCALLY_SAVE_FILE=NO
AMAZON_S3_BASE_URL=https://your-cdn.cloudfront.net
S3_BUCKET_NAME=your-bucket-name

# Admin Credentials
ADMIN_CLIENT_ID=admin
ADMIN_CLIENT_KEY=admin

# API Configuration
API_URL=http://127.0.0.1:5000
```

---

### STEP 5: Update Application Configuration

**Modify `app.py`** to prevent creating template tables:

Find this section (around line 71-79):
```python
@app.on_event("startup")
async def start_scheduling():
    """This creates all tables stored in the Base.metadata(example:models_user,models_product).
    Conditional by default, will not attempt to recreate tables already present in the target database.
    """
    Base.metadata.create_all(bind=engine)
    AbstractBase.metadata.create_all(bind=engine)
    bulk_insert_from_json_file()
    db.refresh_metadata()
```

**Comment out the table creation** since you're using an existing database:
```python
@app.on_event("startup")
async def start_scheduling():
    """Using existing database schema - skipping table creation"""
    # Base.metadata.create_all(bind=engine)  # COMMENTED OUT
    # AbstractBase.metadata.create_all(bind=engine)  # COMMENTED OUT
    # bulk_insert_from_json_file()  # COMMENTED OUT
    db.refresh_metadata()  # Keep this to load existing tables
```

---

### STEP 6: Run the Application

```bash
# Start the FastAPI application
python app.py
```

**Expected Output:**
```
>>>>>Connecting to the database
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

---

## VALIDATION STEPS

### ✅ Test 1: Health Check

```bash
curl http://127.0.0.1:5000/api/health-check
```

**Expected Response:**
```json
{"message": "Application running sucessfully"}
```

---

### ✅ Test 2: Access Swagger UI

Open your browser and navigate to:
```
http://127.0.0.1:5000/docs
```

You should see the FastAPI Swagger documentation with all available endpoints.

---

### ✅ Test 3: Verify Database Connection

```bash
# Check if application can access your tables
mysql -u root -p fastkyc -e "SELECT COUNT(*) as total_customers FROM customer1;"
```

---

### ✅ Test 4: Test API Endpoints

Using the Swagger UI (`http://127.0.0.1:5000/docs`):

1. **Try the health check endpoint**
   - Expand `/api/health-check`
   - Click "Try it out"
   - Click "Execute"
   - Should return 200 OK

2. **Test database queries** (if you have endpoints configured)
   - Look for endpoints related to your tables (customers, features, etc.)
   - Test GET requests to retrieve data

---

### ✅ Test 5: Check Application Logs

Monitor the terminal where you ran `python app.py` for any errors or warnings.

---

## Common Issues & Solutions

### Issue 1: Connection Error
**Error:** `Can't connect to MySQL server`

**Solution:**
1. Verify MySQL is running: `sudo systemctl status mysql` (Linux) or check Services (Windows)
2. Check credentials in `.env` file
3. Verify database name is correct: `fastkyc`

---

### Issue 2: Import Errors
**Error:** `ModuleNotFoundError: No module named 'pymysql'`

**Solution:**
```bash
pip install pymysql
# or
poetry add pymysql
```

---

### Issue 3: Table Not Found
**Error:** `Table 'fastkyc.some_table' doesn't exist`

**Solution:**
1. Verify SQL dump was imported correctly:
   ```bash
   mysql -u root -p fastkyc -e "SHOW TABLES;"
   ```
2. Re-import if needed:
   ```bash
   mysql -u root -p fastkyc < "fastkyc_dump_1_5 (1).sql"
   ```

---

### Issue 4: Port Already in Use
**Error:** `Address already in use`

**Solution:**
- Change port in `app.py` (line 254):
  ```python
  uvicorn.run(app, host="127.0.0.1", port=8000)  # Changed from 5000 to 8000
  ```

---

## Next Steps After Validation

Once everything is working:

1. **Review your routers** in the `routers/` directory
2. **Update authentication logic** in `utils/authentication.py`
3. **Configure your API endpoints** to work with your tables
4. **Test all CRUD operations** for your main tables
5. **Set up proper error handling**
6. **Configure production settings** (disable debug mode, set proper secrets)

---

## Quick Reference Commands

```bash
# Start application
python app.py

# Check MySQL connection
mysql -u root -p -e "SHOW DATABASES;"

# View application logs
# (Check the terminal where app.py is running)

# Stop application
# Press CTRL+C in the terminal

# Restart MySQL (if needed)
# Linux: sudo systemctl restart mysql
# Windows: Restart MySQL service from Services
# macOS: brew services restart mysql
```

---

## Application is Ready! 🎉

If all validation steps pass, your FastKYC application is successfully set up and running with your existing MySQL database.

Access your application at:
- **API**: http://127.0.0.1:5000
- **Swagger Docs**: http://127.0.0.1:5000/docs
- **ReDoc**: http://127.0.0.1:5000/redoc

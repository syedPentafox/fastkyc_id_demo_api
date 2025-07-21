# Digital Command Centre for DICGC Operations (DICGC)

🚀 **Project Overview**
---
This project, **Digital Command Centre for DICGC Operations**, aims to provide a comprehensive framework for rapid application development with minimal coding requirements. Leveraging cutting-edge technologies, it streamlines the development process, making it ideal for projects requiring speed, agility, and efficiency.

---

## 📚 **Table of Contents**
- [✨ Features](#-features)
- [💻 Tech Stack](#-tech-stack)
- [🔧 Prerequisites](#-prerequisites)
- [🚀 Getting Started](#-getting-started)

---

## ✨ **Features**
- 🔐 **Authentication:** OAuth2 with Password (and hashing), Bearer with JWT tokens
- 🗄️ **ORM:** SQL Alchemy
- 📦 **Package Manager:** Poetry
- 📜 **Documentation:** Swagger UI, ReDoc

---

## 💻 **Tech Stack**
- **Backend:**
  - Python - FastAPI Framework
  - PostgreSQL (Database)

---

## 🔧 **Prerequisites**

### ✅ **Software Requirements**
- **Python 3.10+** ([Installation Guide](https://docs.python.org/3/using/index.html))
- **Git** ([Download](https://github.com/git-guides/install-git))
- **Command Line Tools** (e.g., Windows Command Prompt or PowerShell)
- **Integrated Development Environments (IDE):**
  - [Visual Studio](https://visualstudio.microsoft.com/vs/community/)
  - [PyCharm](https://www.jetbrains.com/pycharm/download/)
- **Poetry** ([Installation Guide](https://python-poetry.org/docs/))
- **PostgreSQL** ([Download](https://www.postgresql.org/download/))
- **Insomnia** ([Download](https://insomnia.rest/download))

### 🐍 **Installing Python**
Install Python with a stable version >= 3.10. Ensure you add Python to the PATH environment variable.

![Add Python Path](https://studyopedia.com/wp-content/uploads/2020/10/4.-Python-3.9-installation-started.png)

---

## 🚀 **Getting Started**

### 1️⃣ Clone the Repository
Navigate to the desired directory and clone the repository:
```bash
# Get the latest snapshot
git clone https://gnanaprakasam@bitbucket.org/dprabh3/my-repo.git
```

### 2️⃣ Open the Project
Open the created local repository in your IDE.

### 3️⃣ Set Up Virtual Environment
Create and activate a virtual environment:
```bash
# Create a virtual environment
py -3 -m venv <venv-name>

# Activate the virtual environment
# Windows Command Prompt
.\<venv-name>\Scripts\activate.bat

# Windows PowerShell
<venv-name>\Scripts\activate
```


### 4️⃣ Install Dependencies
Install packages using Poetry:
```bash
# Install from poetry.lock
poetry install

# Install new packages
poetry add <package-name>
```

### 5️⃣ Add Environment Variables
Create a `.env` file with the following keys:

| **Variable**              | **Description**                              | **Default Value**                                           | **Example Value**                                              |
|---------------------------|----------------------------------------------|-------------------------------------------------------------|--------------------------------------------------------------|
| `DATABASE_URL`            | URL for database connection                 | `postgresql://user:password@localhost/dbname`               | `postgresql://postgres:root@localhost/pnc`                   |
| `AMAZON_S3_BASE_URL`      | Base URL for Amazon S3                      | `https://example.cloudfront.net`                            | `https://example.cloudfront.net`                             |
| `S3_BUCKET_NAME`          | Name of the S3 bucket                       | `example-bucket`                                            | `bucket_name`                                                |
| `JWT_SECRET_KEY`          | Secret key for JWT                          | `your-jwt-secret-key`                                       | `6dcaa22947e965f1c7ae06f1ec6d4f7ebcf603a5578541574883fb700c97ade2` |
| `ACCESS_TOKEN_EXPIRE_HOURS`| Access token expiry in hours                | `1`                                                         | `240`                                                        |
| `REFRESH_TOKEN_EXPIRE_HOURS`| Refresh token expiry in hours              | `24`                                                        | `240`                                                        |
| `AES_SECRET_KEY`          | AES encryption key                          | `your-aes-secret-key`                                       | `GfdfnoffoZdkpo13244@#%(&@###@s34`                           |
| `ALLOWED_ORIGINS`         | Allowed origins for CORS                    | `http://localhost:3000`                                     | `http://localhost:3000`                                      |
| `LOCALLY_SAVE_FILE`       | Save files locally (YES/NO)                 | `NO`                                                        | `YES`                                                        |
| `ADMIN_CLIENT_ID`         | Admin client ID                             | `admin-id`                                                  | `admin`                                                      |
| `ADMIN_CLIENT_KEY`        | Admin client key                            | `admin-key`                                                 | `admin`                                                      |
| `API_URL`                 | Base URL for the API                        | `http://localhost:8000`                                     | `http://127.0.0.1:8000`                                      |

---
# **🔧 Alembic Setup and Usage Guide**

## **1. 🚀 Install Alembic and PostgreSQL Driver**

First, install Alembic and the PostgreSQL driver for Python (`psycopg2`).

```bash
pip install alembic psycopg2
```

---

## **2. 📂 Initialize Alembic**

Initialize Alembic in your project directory to create the migration folder and configuration files.

```bash
alembic init migrations
```

📁 This creates a `migrations/` directory and an `alembic.ini` configuration file.

---

## **3. ⚙️ Configure Alembic for PostgreSQL**

### **📝 Update `alembic.ini`**

Open the `alembic.ini` file and set the `sqlalchemy.url` to your PostgreSQL connection string.

```ini
sqlalchemy.url = postgresql+psycopg2://username:password@localhost/dbname
```

🔑 Replace `username`, `password`, `localhost`, and `dbname` with your PostgreSQL database credentials.

### **🔗 Link SQLAlchemy Models**

In the `migrations/env.py` file, link your SQLAlchemy models by updating the `target_metadata`.

```python
from myapp.models import Base  # Adjust this to your models file

target_metadata = Base.metadata
```

🔍 This allows Alembic to detect changes in your models and generate migration scripts.

---

## **4. ✏️ Create a Migration Script**

Whenever you make changes to your models (e.g., adding new columns or tables), generate a migration script using:

```bash
alembic revision --autogenerate -m "Describe changes"
```

📜 This generates a new migration script in the `migrations/versions/` folder.

---

## **5. 📤 Apply Migrations**

To apply the migrations to the database, run the following command:

```bash
alembic upgrade head
```

✅ This applies all pending migrations and brings your database schema up to date.

---

## **6. 📖 View Migration History**

To view the history of migrations, run:

```bash
alembic history
```

📚 This will list all migration scripts that have been applied.

---

## **7. ⏪ Rollback Migrations**

If you need to rollback a migration, use the following command:

```bash
alembic downgrade -1  # Rollback the last migration
```

🔄 You can also specify a specific revision to rollback to:

```bash
alembic downgrade <revision_id>
```

Replace `<revision_id>` with the identifier of the migration you want to rollback to.

---

## **8. 🛠️ Troubleshooting**

### **⚠️ Target Database is Not Up to Date**

If you see an error like:

```text
Target database is not up to date
```

📌 Run the following command to ensure your database is up to date:

```bash
alembic upgrade head
```

If the issue persists, check the `alembic_version` table in your database to ensure it matches the latest migration revision.

### **🔧 Forcing a Migration Generation**

If Alembic is out of sync but the schema is correct, use:

```bash
alembic stamp head
```

🔖 This marks the database as being at the latest revision, without applying migrations.

---

## **9. 🕒 Rollback to a Specific Revision**

To rollback to a specific migration revision, use the following command:

```bash
alembic downgrade <revision_id>
```

📂 Replace `<revision_id>` with the identifier of the migration (you can find it in the migration script filename).

---

## 📜 **Documentation**
- **Swagger UI:** Interactive API documentation available at `/docs`
- **ReDoc:** Rich API documentation available at `/redoc`

---

💡 Happy Coding! 🌟

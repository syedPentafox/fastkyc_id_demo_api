# =======
# setting up single requirements-all.txt
# =======
rm -rf .venv
curl -sSL https://install.python-poetry.org | python3 -
python3 -m venv .venv
source .venv/bin/activate
poetry install

# manually comment out the packages that give error on pip install and keep installing using pip
pip install -r requirements.txt.bkp

pip freeze > requirements-all.txt

# =======
# downloading packages
# =======
pip download -r requirements-all.txt -d packages
pip download setuptools wheel pip -d packages
pip download fastapi==0.115.13 boto3==1.38.38 pydantic[email] cx_Oracle oracledb -d packages
rm packages.zip
zip -r packages.zip packages

# postgres and oracle db dependencies
dnf download --destdir rpms --resolve libaio postgresql-devel
rm rpms.zip
zip -r rpms.zip rpms
wget https://download.oracle.com/otn_software/linux/instantclient/2112000/el9/instantclient-basic-linux.x64-21.12.0.0.0dbru.el9.zip

# =======
# commands for server without internet
# =======

# inside project directory
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate

# wherever packages.zip, rpms.zip, instantclient-basic-linux.x64-21.12.0.0.0dbru.el9.zip and requirements-all.txt are located
rm -rf packages
unzip packages.zip
unzip rpms.zip
unzip instantclient-basic-linux.x64-21.12.0.0.0dbru.el9.zip

# install all python dependencies
pip install --no-index --find-links=packages -r requirements-all.txt
pip install --no-index --find-links=packages fastapi boto3 pydantic[email] cx_Oracle oracledb

# oracle db dependency
export LD_LIBRARY_PATH=/home/ec2-user/instantclient_21_12:$LD_LIBRARY_PATH

# installing postgres and oracle dependencies
sudo yum localinstall rpms/*.rpm

# inside project directory
uvicorn app:app --reload --host 127.0.0.1 --port 5000
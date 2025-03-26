#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting AutoDFBench Framework Setup..."

# Load environment variables from .env
if [ -f ".env" ]; then
    echo "📦 Loading environment variables from .env..."
    while IFS='=' read -r key value; do
        if [[ ! "$key" =~ ^# && -n "$key" ]]; then
            value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//')
            export "$key=$value"
        fi
    done < .env
else
    echo "⚠️ .env file not found!"
    exit 1
fi


# Check if required environment variables are set
if [[ -z "$DB_HOST" || -z "$DB_PORT" || -z "$DB_USER" || -z "$DB_PASSWORD" || -z "$DB_NAME" ]]; then
    echo "❌ Error: Missing database environment variables in .env file."
    exit 1
fi

# 1. Install MySQL (if not installed)
if ! command -v mysql &> /dev/null; then
    echo "🔧 Installing MySQL..."
    sudo apt update
    sudo apt install -y mysql-server
    sudo systemctl enable mysql
    sudo systemctl start mysql
else
    echo "✅ MySQL is already installed."
fi

#2. Setup MySQL Database and User
echo "🔑 Setting up MySQL database and user..."

# Ensure the password is properly escaped
ESCAPED_PASS="$DB_PASSWORD"

# Run MySQL commands with correct syntax
sudo mysql -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;"
sudo mysql -e "CREATE USER IF NOT EXISTS $DB_USER@'%' IDENTIFIED BY $DB_PASSWORD;"
sudo mysql -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO $DB_USER@'%';"
sudo mysql -e "FLUSH PRIVILEGES;"


echo "✅ MySQL setup complete."

# 3. Import Database Schema from SQL File
SQL_FILE="database/DFLLM.sql"
DB_HOST=$(echo "$DB_HOST" | sed "s/^'//;s/'$//")
DB_USER=$(echo "$DB_USER" | sed "s/^'//;s/'$//")
DB_PASSWORD=$(echo "$DB_PASSWORD" | sed "s/^'//;s/'$//")
DB_NAME=$(echo "$DB_NAME" | sed "s/^'//;s/'$//")

if [ -f "$SQL_FILE" ]; then
    echo "📂 Importing database schema from $SQL_FILE..."
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$SQL_FILE"
    echo "✅ Database imported successfully."
else
    echo "⚠️ Warning: SQL file '$SQL_FILE' not found. Skipping database import."
fi

# 4. Install Miniconda (if not installed)
if ! command -v conda &> /dev/null; then
    echo "🐍 Installing Miniconda..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    export PATH="$HOME/miniconda/bin:$PATH"
    echo 'export PATH="$HOME/miniconda/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
else
    echo "✅ Conda is already installed."
fi

# 5. Create Conda Environment from environment.yml
if [ -f "environment.yml" ]; then
    ENV_NAME=$(grep 'name:' environment.yml | awk '{print $2}')
    
    if conda env list | grep -q "$ENV_NAME"; then
        echo "✅ Conda environment '$ENV_NAME' already exists."
    else
        echo "🌱 Creating Conda environment '$ENV_NAME' from environment.yml..."
        conda env create -f environment.yml
        echo "✅ Conda environment '$ENV_NAME' created."
    fi
else
    echo "❌ Error: environment.yml not found. Please add it to the project directory."
    exit 1
fi

echo "🎉 Setup Complete! Run 'conda activate $ENV_NAME' to start your environment."

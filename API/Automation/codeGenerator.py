import os
import re
import csv
import sys
import mysql.connector

job_id = sys.argv[1]
base_test_case_arg = sys.argv[2] if len(sys.argv) > 2 else 0

# Database configuration (replace with your actual database credentials)
DB_HOST = '192.168.1.100'
DB_USER = 'root'
DB_PASSWORD = '19891209'
DB_NAME = 'DFLLM'

# Function to establish a connection to the database
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to determine the type of code and return the appropriate file extension
def get_file_extension(code):
    if code.strip().startswith("#!/bin/bash") or "bash" in code:
        return "sh"
    elif "python" in code or re.search(r"def |import ", code):
        return "py"
    else:
        return "txt"  # default to txt if the type is unknown

# Function to fetch code data from the database
def fetch_code_data():
    conn = get_db_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        # Fetch data from the prompt_codes table
        if base_test_case_arg == 0:
             query = f"SELECT * FROM prompt_codes WHERE job_id = '{job_id}'"
        else:
            query = f"SELECT * FROM prompt_codes WHERE job_id = '{job_id}' and base_test_case = '{base_test_case_arg}'"
        
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()

        return result
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []

# Function to update the file_path in the database
def update_file_path_in_db(record_id, new_file_path):
    conn = get_db_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        update_query = "UPDATE prompt_codes SET file_path = %s WHERE id = %s"
        cursor.execute(update_query, (new_file_path, record_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False

# Function to set execution permission on a file
def set_execution_permission(file_path):
    try:
        os.chmod(file_path, 0o755)
    except Exception as e:
        print(f"Error setting execution permission for {file_path}: {e}")

# Function to ensure Unix-style line endings
def convert_to_unix_line_endings(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().replace('\r\n', '\n')
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
    except Exception as e:
        print(f"Error converting to Unix line endings for {file_path}: {e}")

# Function to process database records and create separate files for each code snippet
def process_db_records(records, output_folder):
    output_data = []

    for row in records:
        record_id = row["id"]
        code = row["code"]
        base_test_case = row["base_test_case"]
        model = row["model"]
        
        if not code.strip():
            continue  # Skip if the code field is empty
        
        # Determine the file extension based on the code type
        file_extension = get_file_extension(code)
        script_type = file_extension

        output_job_folder_path = os.path.join(output_folder, job_id)
        output_model_folder_path = os.path.join(output_job_folder_path, model)
        
        output_folder_path = os.path.join(output_model_folder_path, base_test_case)
        
        # Create the file name based on the row ID and extension
        file_name = f"row_{record_id}.{file_extension}"
        file_path = os.path.join(output_folder_path, file_name)
        
        # Ensure the directory exists
        os.makedirs(output_folder_path, exist_ok=True)
        
        # Write the code to the file with Unix-style line endings
        with open(file_path, mode='w', newline='\n') as code_file:
            code_file.write(code)
        
        # Convert any existing CRLF line endings to LF
        convert_to_unix_line_endings(file_path)
        
        # Set execution permission on the created file
        set_execution_permission(file_path)
        
        # Update the file_path in the database
        update_file_path_in_db(record_id, file_path)
        
        # Collect data for the new CSV
        output_data.append({"path": file_path, "script_type": script_type})
    
    return output_data

# Main function
def main():
    output_base_folder = "../output_code_files"
    output_csv_path = os.path.join(output_base_folder, "output_paths.csv")
    
    # Create the output base folder if it doesn't exist
    os.makedirs(output_base_folder, exist_ok=True)
    
    # Fetch data from the database
    records = fetch_code_data()
    if not records:
        print("No data found in the prompt_codes table.")
        return False

    # Process the records and collect the output data
    output_data = process_db_records(records, output_base_folder)

    # Write the collected data to the new CSV file
    with open(output_csv_path, mode='w', newline='') as outfile:
        csv_writer = csv.DictWriter(outfile, fieldnames=["path", "script_type"])
        csv_writer.writeheader()
        csv_writer.writerows(output_data)

    print(f"All paths have been written to {output_csv_path}")
    return True

if __name__ == "__main__":
    main()

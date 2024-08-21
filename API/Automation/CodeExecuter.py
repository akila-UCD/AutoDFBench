import subprocess
import os
import shutil  # Import shutil to copy files
import mysql.connector
import sys
from mysql.connector import Error

job_id = sys.argv[1]

# Function to check and copy necessary disk image files
def check_and_copy_disk_images():
    required_files = ["ss-unix-07-25-18.dd", "ss-win-07-25-18.dd"]
    source_folder = "/home/ubuntu/API/"
    destination_folder = "/home/ubuntu/API/DISKIMAGES"

    os.makedirs(destination_folder, exist_ok=True)

    for file_name in required_files:
        source_path = os.path.join(source_folder, file_name)
        dest_path = os.path.join(destination_folder, file_name)

        if not os.path.exists(dest_path):
            print(f"{file_name} not found in {destination_folder}. Copying from {source_folder}.")
            try:
                shutil.copy(source_path, dest_path)
                print(f"Copied {file_name} to {destination_folder}.")
            except Exception as e:
                print(f"Failed to copy {file_name}: {e}")
                return False
        else:
            print(f"{file_name} already exists in {destination_folder}.")
    return True

# Function to execute a script and capture its output with a timeout
def execute_script(file_path, output_folder):
    if not check_and_copy_disk_images():
        return "", "Error: Failed to ensure disk images are available."

    try:
        print(f"Executing script: {file_path}")
        output_file_path = os.path.join(output_folder, os.path.basename(file_path) + ".out")
        with open(output_file_path, "w") as output_file:
            if file_path.endswith(".py"):
                # Execute Python script
                result = subprocess.run(["/root/miniconda3/envs/dfllm_eval/bin/python3", file_path], stdout=output_file, stderr=subprocess.PIPE, text=True, timeout=300)
            elif file_path.endswith(".sh"):
                # Execute Shell script
                result = subprocess.run(["/usr/bin/sh", file_path], stdout=output_file, stderr=subprocess.PIPE, text=True, timeout=300)
            else:
                return "", "Unsupported script type"
        
        if result.returncode == 0:
            with open(output_file_path, "r") as f:
                return f.read(), ""
        else:
            return "", result.stderr
    except subprocess.TimeoutExpired:
        return "", "Error: Execution timed out"
    except Exception as e:
        return "", f"Exception: {str(e)}"

# Function to create subfolder from the second directory name in the file path
def create_subfolder(file_path, base_folder):
    parts = file_path.split(os.sep)
    if len(parts) > 2:
        subfolder = parts[1]
        subfolder_path = os.path.join(base_folder, subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        return subfolder_path
    else:
        return base_folder

# Function to process the paths from the database and execute scripts
def process_scripts(conn, base_folder, output_folder):
    try:
        conn.reconnect()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT file_path, script_type, model FROM prompt_codes WHERE job_id = %s"
        cursor.execute(query, (job_id,))
        rows = cursor.fetchall()

        for row in rows:
            file_path = row["file_path"]
            script_type = row["script_type"]
            model = row["model"]

            if not file_path:
                continue
            # Create subfolder from the second directory name
            subfolder_path = create_subfolder(file_path, base_folder)
            
            # Execute the script and capture the output and error
            result, error = execute_script(file_path, output_folder)
            
            # Construct the testcase name
            relative_path = os.path.relpath(file_path, start="../output_code_files")
            testcase = os.path.splitext(relative_path.replace(os.sep, '_'))[0]
            
            # Extract base_test_case from testcase
            base_test_case = '_'.join(testcase.split('_')[:-2])

            # Extract specific hits from the result
            deleted_files_hits, active_file_hits, unallocated_file_hits = count_hits(result)

            # Insert the result into the database
            insert_result_to_db(conn, testcase, base_test_case, model, script_type, result, active_file_hits, deleted_files_hits, unallocated_file_hits, error)
            print(f"Processed {file_path} with result: {result[:50]}... and error: {error[:50]}...")  # Print the first 50 chars of result and error for brevity

    except Error as e:
        print(f"Error: {e}")

# Function to count the types of hits in the result
def count_hits(result):
    deleted_files_hits = 0
    active_file_hits = 0
    unallocated_file_hits = 0
    print(result)
    for line in result.splitlines():
        # Skip empty lines
        if not line.strip():
            continue

        # Parse the line
        parts = line.split(',')
        if len(parts) != 2:
            continue

        path, status = parts
        if status.strip() == 'deleted':
            deleted_files_hits += 1
        elif status.strip() == 'active':
            active_file_hits += 1
        elif status.strip() == 'unallocated':
            unallocated_file_hits += 1
    
    return deleted_files_hits, active_file_hits, unallocated_file_hits

# Function to insert the result into the database
def insert_result_to_db(conn, testcase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error):
    try:
        conn.reconnect()
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results ( testCase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error, job_id)
            VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (testcase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error, job_id))
        conn.commit()
    except Error as e:
        print(f"Error: {e}")

# Main function
def main():
    base_folder = "../output_code_files"
    output_folder = "../outputfiles"
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Database connection
    conn = mysql.connector.connect(
        host="192.168.1.100",
        user="root",
        password="19891209",
        database="DFLLM"
    )

    try:
        print("Starting script execution.")
        process_scripts(conn, base_folder, output_folder)
        print("Script execution completed.")
        return True
    finally:
        if conn.is_connected():
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()

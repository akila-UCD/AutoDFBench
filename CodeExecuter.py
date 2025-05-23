import subprocess
import os
import shutil  # Import shutil to copy files
import mysql.connector
import sys
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

job_id = sys.argv[1]
base_test_case_arg = sys.argv[2] if len(sys.argv) > 2 else 0


# Accessing the database settings from the environment variables
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')


# Function to check and copy necessary disk image files
def check_and_copy_disk_images():
    required_files = ["ss-unix-07-25-18.dd", "ss-win-07-25-18.dd"]
    source_folder = os.getenv('DISK_IMAGE_SOURCE_FOLDER')
    destination_folder = os.getenv('DISK_IMAGE_DESTINATION_FOLDER')

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
        print(f"Executing script..: {file_path}")
        output_file_path = os.path.join(output_folder, os.path.basename(file_path) + ".out")
        with open(output_file_path, "w") as output_file:
            if file_path.endswith(".py"):
                # Execute Python script

                result = subprocess.run([os.getenv('CONDA_EXECUTE_ENV'), file_path], stdout=output_file, stderr=subprocess.PIPE, text=True, timeout=300)

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

def get_job_data(conn):

    if conn is None:
        return []
    
    try:
        conn.reconnect()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM job WHERE id = '{job_id}'"
       
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()

        return result
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []

# Function to process the paths from the database and execute scripts
def process_scripts(conn, base_folder, output_folder):
    try:  
        jobData = get_job_data(conn)
        # for row in jobData:
        #     take_in_test_count = row["take_in_test_count"]

        conn.reconnect()
        cursor = conn.cursor(dictionary=True)
       

        if base_test_case_arg == 0:
            query = "SELECT file_path, script_type, model, id FROM prompt_codes WHERE job_id = %s and `code_execution` IS NULL ORDER BY `prompt_codes`.`base_test_case` ASC"
        else:
            query = f"SELECT file_path, script_type, model, id FROM prompt_codes WHERE job_id = %s and base_test_case = '{base_test_case_arg}' and `code_execution` IS NULL"
        
        cursor.execute(query, (job_id,))
        rows = cursor.fetchall()

        for row in rows:
            file_path = row["file_path"]
            script_type = row["script_type"]
            model = row["model"]
            prompt_code_id = row["id"]

            if not file_path:
                continue
            # Create subfolder from the second directory name
            subfolder_path = create_subfolder(file_path, base_folder)
            print(file_path)
            # Execute the script and capture the output and error
            result, error = execute_script(file_path, output_folder)

            if jobData[0]['cftt_task'] == 'string_search':
                print('stringsearch') 
                 # Construct the testcase name
                relative_path = os.path.relpath(file_path, start="../output_code_files")
                testcase = os.path.splitext(relative_path.replace(os.sep, '_'))[0]
                
                # Extract base_test_case from testcase
                base_test_case = '_'.join(testcase.split('_')[:-2])

                # Extract specific hits from the result
                deleted_files_hits, active_file_hits, unallocated_file_hits = count_hits(result)

                # Insert the result into the database
                insert_result_to_db(conn, testcase, base_test_case, model, script_type, result, active_file_hits, deleted_files_hits, unallocated_file_hits, error, prompt_code_id)
                print(f"Processed {file_path} with result: {result[:50]}... and error: {error[:50]}...")  # Print the first 50 chars of result and error for brevity

            else:
                print('not stringsearch')
                # Construct the testcase name
                relative_path = os.path.relpath(file_path, start="../output_code_files")
                testcase = os.path.splitext(relative_path.replace(os.sep, '_'))[0]
                
                # Extract base_test_case from testcase
                base_test_case = '_'.join(testcase.split('_')[:-2])
                # results_set = seperate_dfr_data(result)
                print(result)
                # os._exit(1) 
                insert_result_to_db(conn, testcase, base_test_case, model, script_type, result, 0, 0, 0, error, prompt_code_id)
                os._exit(1)
               
                
            

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
def insert_result_to_db(conn, testcase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error, prompt_code_id):
    try:
        conn.reconnect()
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results ( testCase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error, job_id)
            VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
        """
        cursor.execute(insert_query, (testcase, base_test_case, model, script_type, results, active_file_hits, deleted_files_hits, unallocated_file_hits, error, job_id))
        updateQuery = f"UPDATE `prompt_codes` SET `code_execution` = '1' WHERE `prompt_codes`.`id` = {prompt_code_id}"
        cursor.execute(updateQuery)
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
        host = DB_HOST,
        user = DB_USER,
        password = DB_PASSWORD,
        database = DB_NAME
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

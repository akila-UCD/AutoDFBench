import os
import re
import subprocess
import sys
import mysql.connector
from mysql.connector import Error

job_id = sys.argv[1]

def extract_code(response_text):
    # Pattern to match code blocks with language specified or just generic blocks
    code_block_pattern = re.compile(r"```(python|bash|sh)?(.*?)```", re.DOTALL)
    generic_code_pattern = re.compile(r"```(.*?)```", re.DOTALL)
    
    # First, check for language-specific code blocks
    matches = code_block_pattern.findall(response_text)
    if matches:
        for match in matches:
            language, code = match
            if language == 'python':
                return code.strip(), "python"
            elif language in ('bash', 'sh'):
                return code.strip(), "bash"
    
    # If no language-specific block is found, check for generic code blocks
    generic_match = generic_code_pattern.search(response_text)
    if generic_match:
        return generic_match.group(1).strip(), "generic"
    
    # Fallback: Look for common patterns indicating code
    python_pattern = re.compile(r"(?:def |import |class )")
    bash_pattern = re.compile(r"(?:#!/bin/bash|echo |sudo |apt-get )")
    
    # Search for Python code based on common patterns
    python_code_match = python_pattern.search(response_text)
    if python_code_match:
        return python_code_match.group().strip(), "python"
    
    # Search for Bash code based on common patterns
    bash_code_match = bash_pattern.search(response_text)
    if bash_code_match:
        return bash_code_match.group().strip(), "bash"

    return "", ""

# Function to execute a script and capture its output with a timeout
def execute_script(file_path, output_folder):
    try:
        print(f"Executing script: {file_path}")
        output_file_path = os.path.join(output_folder, os.path.basename(file_path) + ".out")
        with open(output_file_path, "w") as output_file:
            if file_path.endswith(".py"):
                # Execute Python script
                result = subprocess.run(["python", file_path], stdout=output_file, stderr=subprocess.PIPE, text=True, timeout=60)
            elif file_path.endswith(".sh"):
                # Execute Shell script
                result = subprocess.run(["bash", file_path], stdout=output_file, stderr=subprocess.PIPE, text=True, timeout=60)
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

# Function to update the code and file_path in the database
def update_code_and_file_path(conn, row_id, code, file_path):
    try:
        cursor = conn.cursor()
        update_query = "UPDATE prompt_codes SET code = %s, file_path = %s WHERE id = %s"
        cursor.execute(update_query, (code, file_path, row_id))
        conn.commit()
        print(update_query)
    except Error as e:
        print(f"Error: {e}")

# Main function to extract and process code snippets
def main():
    base_folder = "output_code_files"
    output_folder = "outputfiles"
    
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
        print("Starting code extraction and processing.")
        
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, response, base_test_case FROM prompt_codes WHERE file_path is NULL AND job_id = %s"
        cursor.execute(query, (job_id,))
        rows = cursor.fetchall()

        for row in rows:
            response = row["response"]
            row_id = row["id"]
            base_test_case = row["base_test_case"]

            # Extract code from response
            code, script_type = extract_code(response)
            print(script_type)
            print(code)
            # os._exit(1)
            if code:
                # Determine the file extension and script type
                if script_type == "python":
                    extension = "py"
                elif script_type == "bash":
                    extension = "sh"
                elif script_type == "generic":
                    extension = "sh"
                else:
                    continue  # Skip if the script type is unsupported

                # Create the file path
                output_dir = os.path.join(base_folder, base_test_case)
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, f"row_{row_id}.{extension}")
                print(file_path)
                # Write the code to the file
                with open(file_path, "w") as code_file:
                    code_file.write(code)
                print(file_path)
                # Update the database with the code and file path
                update_code_and_file_path(conn, row_id, code, file_path)
        
        print("Code extraction and processing completed.")
        return True
    finally:
        if conn.is_connected():
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()

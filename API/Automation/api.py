import csv
import json
import os
import re
import requests
import mysql.connector
import subprocess
import llm
import time
import sys

specified_column = sys.argv[2] if len(sys.argv) > 2 else None
job_id = sys.argv[1] if len(sys.argv) > 1 else None

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

# Function to fetch DISK_IMAGE_PATH from the MySQL database
def fetch_disk_image_path(disk_image):
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        # Determine the column name in the config table
        config_column = 'windows_disk_path' if disk_image == 'windows_disk_path' else 'linux_disk_path'

        # Execute query to fetch the path
        query = f"SELECT value FROM config WHERE type = '{config_column}'"
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return result[0]  # Return the value from the first row
        else:
            raise Exception(f"No path found for type '{config_column}'.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to fetch PROMPT from the MySQL database
def fetch_base_prompt(base_prompt_id):
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        # Execute query to fetch the prompt
        query = f"SELECT id, prompt FROM base_prompt WHERE id = '{base_prompt_id}'"

        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return result  # Return the ID and prompt
        else:
            raise Exception(f"No prompt found for id = {base_prompt_id}.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def getConfigValues(VALUE_TYPE):
    conn = get_db_connection()

    if conn is None:
        return None
    try:
        cursor = conn.cursor(buffered=True)
        # Execute query to fetch job details where status is 'queued'
        query = f"SELECT `value` FROM `config` WHERE `type` = '{VALUE_TYPE}'"

        cursor.execute(query)
        result = cursor.fetchone() 
        cursor.close()
        conn.close()

        if result:
            return result[0]  # Return the ID and prompt
        else:
            raise Exception(f"No settings found for  = {VALUE_TYPE}.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def get_api_url():

    conn = get_db_connection()

    if conn is None:
        return None
    try:

        modelAPI = f"{model_to_use}_API"
        cursor = conn.cursor(buffered=True)
        # Execute query to fetch job details where status is 'queued'
        query = f"SELECT `value` FROM `config` WHERE `type` = '{modelAPI}'"
        # print(query)

        cursor.execute(query)
        result = cursor.fetchone() 
        cursor.close()
        conn.close()
        print(result)
        if result:
            return result[0]  # Return the ID and prompt
        else:
            raise Exception(f"No settings found for  = {modelAPI}.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to fetch job details from the MySQL database
def fetch_job_details():
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        # Execute query to fetch job details where status is 'queued'
        query = f"SELECT id, take_in_test_count, CAST(model_to_use AS CHAR) as string_value, disk_image, CAST(script_type_need AS CHAR) as string_value, base_prompt_id FROM job WHERE id = '{job_id}'"
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        
        jobs = []
        for row in result:
            jobs.append({
                "id": row[0],
                "take_in_test_count": row[1],
                "model_to_use": row[2],
                "disk_image": row[3],
                "script_type_need": row[4],
                "base_prompt_id": row[5]
            })
        return jobs
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to update job status
def update_job_status(job_id, status):
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        # Update query to set job status
        query = "UPDATE job SET status = %s WHERE id = %s"
        cursor.execute(query, (status, job_id))
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

# Function to send API request
def send_api_request(prompt, base_prompt, disk_image_path, script_type_prompt, model_to_use):
    final_prompt = base_prompt.replace("{prompt}", prompt).replace("{DISK_IMAGE_PATH}", disk_image_path) + script_type_prompt

    # url = "http://192.168.1.12:11434/api/generate"  # Replace with the actual API URL
    url = get_api_url()
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_to_use,
        "prompt": final_prompt,
        "stream": False
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"response : {response}")
    return response.json()

# Function to extract code from the response text
def extract_code(response_text):
    if response_text is None:
        return "", ""  # Return empty strings if the response_text is None

    python_pattern = re.compile(r"```python(.*?)```", re.DOTALL)
    bash_pattern = re.compile(r"```bash(.*?)```", re.DOTALL)
    generic_pattern = re.compile(r"```(.*?)```", re.DOTALL)
    
    python_match = python_pattern.search(response_text)
    bash_match = bash_pattern.search(response_text)
    generic_match = generic_pattern.search(response_text)
    
    if python_match:
        return python_match.group(1).strip(), "python"
    elif bash_match:
        return bash_match.group(1).strip(), "bash"
    elif generic_match:
        return generic_match.group(1).strip(), "generic"
    else:
        return "", ""

# Function to insert data into prompts_codes table
def insert_prompt_code_data(data):
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO prompt_codes (base_test_case, prompt, created_at, response, done, total_duration, prompt_eval_count, 
                                   prompt_eval_duration, eval_count, eval_duration, code, model, disk_type, 
                                   script_type, base_prompt_id, job_id) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, data)
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

#External API USE for Claude and GPT 
def externalAPI(prompt, base_prompt, disk_image_path, script_type_prompt, model_to_use):

    final_prompt = base_prompt.replace("{prompt}", prompt).replace("{DISK_IMAGE_PATH}", disk_image_path) + script_type_prompt
    # print(final_prompt)
    model = llm.get_model(model_to_use)
    model.key = getConfigValues('Claude_API_KEY')
    response = model.prompt(final_prompt)
    # print(f"RES:{response}")
    return response


# Read the input CSV file and send API requests
input_file = "EvaluationMatrix-StringSearching-DataSets_v2.csv"
output_folder = "../output"

# Create the output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Fetch all queued jobs
jobs = fetch_job_details()
if not jobs:
    print("No queued jobs to process.")
    exit(0)  # Exit if no job to process

# Process each queued job
for job_details in jobs:
    # Update the job status to 'started'
    update_job_status(job_details['id'], 'started')

    # Fetch the DISK_IMAGE_PATH based on the job's disk_image value
    DISK_IMAGE_PATH = fetch_disk_image_path(job_details['disk_image'])
    if not DISK_IMAGE_PATH:
        raise Exception("Failed to retrieve DISK_IMAGE_PATH from the database.")

    # Fetch the base PROMPT
    base_prompt_data = fetch_base_prompt(job_details['base_prompt_id'])
    if not base_prompt_data:
        raise Exception("Failed to retrieve BASE_PROMPT from the database.")
    BASE_PROMPT = base_prompt_data[1]  # Extract the prompt
    base_prompt_id = base_prompt_data[0]  # Extract the base prompt ID

    # Model to use for API request
    model_to_use = job_details['model_to_use']

    # Script type needed
    script_type = job_details['script_type_need']
    script_type_prompt = f" You should provide a {script_type} code to achieve this task"

    with open(input_file, mode='r', newline='') as infile:
        csv_reader = csv.reader(infile)
        
        # Get the header from the input file
        header = next(csv_reader)

        # Determine which columns to process based on the specified column name
        columns_to_process = [col_index for col_index, col_name in enumerate(header) if specified_column is None or col_name == specified_column]

        if not columns_to_process:
            raise Exception(f"Column '{specified_column}' not found in the CSV header.")

         # Process each specified column in the input file
        for col_index in columns_to_process:

            col_name = header[col_index]

            # Create a folder for each column
            col_folder = os.path.join(output_folder, col_name)
            os.makedirs(col_folder, exist_ok=True)
            print(f"Folder created for column: {col_name}")
            
            # Create an output CSV file for the column
            output_file = os.path.join(col_folder, f"{col_name}.csv")
            
            with open(output_file, mode='w', newline='') as outfile:
                csv_writer = csv.writer(outfile)
                
                # Write the header for the output CSV file
                output_header = ["prompt", "model", "created_at", "response", "done", "total_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "code"]
                csv_writer.writerow(output_header)
                
                # Read the number of rows specified in take_in_test_count
                for row_index, row in enumerate(csv_reader):
                    if row_index >= job_details['take_in_test_count']:
                        break
                    
                    csv_line_content = row[col_index]
                    
                    # Send API request
                    if model_to_use == 'claude-3.5-sonnet':
                        api_response =  externalAPI(csv_line_content, BASE_PROMPT, DISK_IMAGE_PATH, script_type_prompt, model_to_use)
                        created_at = time.time()
                        response_text = api_response.text()
                        done = 1
                        total_duration = 0
                        prompt_eval_count = 0
                        prompt_eval_duration = 0
                        eval_count = 0
                        eval_duration = 0
                    else:
                        api_response = send_api_request(csv_line_content, BASE_PROMPT, DISK_IMAGE_PATH, script_type_prompt, model_to_use)
                        created_at = api_response.get("created_at")
                        response_text = api_response.get("response")
                        done = api_response.get("done")
                        total_duration = api_response.get("total_duration")
                        prompt_eval_count = api_response.get("prompt_eval_count")
                        prompt_eval_duration = api_response.get("prompt_eval_duration")
                        eval_count = api_response.get("eval_count")
                        eval_duration = api_response.get("eval_duration")
                    
                    # Extract required fields from the response
                    prompt = csv_line_content
                    base_test_case = col_name
                    model = model_to_use
                    
                    
                    code, code_type = extract_code(response_text)

                    db_data = (
                        base_test_case, prompt, created_at, response_text, done, total_duration, prompt_eval_count,
                        prompt_eval_duration, eval_count, eval_duration, code, model,
                        job_details['disk_image'], script_type, base_prompt_id, job_details['id']
                    )
                    print(f"DB Inset for prompt=> {prompt}")
                    insert_prompt_code_data(db_data)
                    
                    # Write the extracted data to the output CSV file
                    csvData = [prompt, model, created_at, response_text, done, total_duration, prompt_eval_count, prompt_eval_duration, eval_count, eval_duration, code]
                    csv_writer.writerow(csvData)
                   
                    
                print(f"Completed processing for column: {col_name}")
                
                # Reset the reader to the start of the file for the next column
                infile.seek(0)
                next(csv_reader)  # Skip the header again
                if model_to_use == 'claude-3.5-sonnet':
                    time.sleep(30)

    # Run the codeGenerator.py script
    try:
        result = subprocess.run(["python", "codeGenerator.py", str(job_details['id'])], check=True, text=True, capture_output=True)
        if result.returncode == 0:
            print("codeGenerator.py executed successfully.")
            # Update the job status to 'code_execution'
            update_job_status(job_details['id'], 'code_execution')
            result_recheck = subprocess.run(["python", "recheckCodes.py", str(job_details['id'])], check=True, text=True, capture_output=True)

            result_executer = subprocess.run(
                        ["python", "CodeExecuter.py", str(job_details['id'])], 
                        check=True, text=True, capture_output=True
                    )
            if result.returncode == 0:
                print("CodeExecuter.py executed successfully.")
                update_job_status(job_details['id'], 'ended')
            else:
                print("codeGenerator.py did not complete successfully or did not return True.")
        else:
            print("codeGenerator.py did not complete successfully or did not return True.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running codeGenerator.py: {e}")
    
    update_job_status(job_details['id'], 'ended')

print("End")


# **AutoDFBench** Setup Guide

  

## Prerequisites

  

Before starting, ensure that you have the following installed:

-  **MySQL** or **MariaDB** (for database setup)

-  **Miniconda** or **Anaconda** (for environment setup)

-  **Python** (for running the project)

-  **Git** (for cloning the repository)

  

## Steps

 

### Step 1: Clone the Repository

  

First, clone the repository to your local machine:

  

```bash

git  clone  git@github.com:akila-UCD/AutoDFBench.git

cd <cloned-directory>

```

###  IMPORTANT: Rename the .env-sample to .env
 - CONDA_EXECUTE_ENV : Your conda environment. 
 - DISK_IMAGE_SOURCE_FOLDER:   Back Up Folder for disk images 
 - DISK_IMAGE_DESTINATION_FOLDER: Folder for disk images 
 - WINDOWS_DATA_CSV_PATH: Prompts CSV path for windows tests (for CFTT String Search) 
 - UNIX_DATA_CSV_PATH: Prompts CSV path for linx tests (for CFTT String Search)  
 - DELETED_FILE_DATA_CSV_PATH: Prompt CSV path for  CFTT Deleted File Recovery
 - EXTERNAL_MODELS :  External models if using

example:
```bash
CONDA_EXECUTE_ENV='/home/akila/miniconda3/envs/dfllm_eval/bin/python3'
DISK_IMAGE_SOURCE_FOLDER='DD_IMAGES/'
DISK_IMAGE_DESTINATION_FOLDER='/DD_IMAGES'
WINDOWS_DATA_CSV_PATH='Data/Evaluation-Matrix-String-Searching-Windows-DataSets.csv'
UNIX_DATA_CSV_PATH='Data/Evaluation-Matrix-String-Searching-Unix-DataSets.csv'
DELETED_FILE_DATA_CSV_PATH='Data/Evaluation_prompts_deleted_file.recovery.csv'
EXTERNAL_MODELS='claude-3.5-sonnet,gpt-4o'
```
  
### Step 2: Modify the `.env` File (Optional)

The `.env` file contains environment variables for your setup. Ensure it contains the necessary configurations such as:

-   `DB_HOST`
    
-   `DB_USER`
    
-   `DB_PASSWORD`
    
-   `DB_NAME`
    
-   `DB_PORT`
    

Example `.env` file:

```bash
DB_HOST=localhost
DB_USER=root2
DB_PASSWORD=root
DB_NAME=mydatabase
DB_PORT=3306
```

### Step 3: Run the setup.sh Script

  

The setup.sh script will automate the initial setup, including creating the necessary database, setting up the environment, and configuring MySQL users.

  

 1. Make the setup.sh script executable:
```bash 
chmod +x setup.sh
```
	
 2. Run the `setup.sh` script to configure the environment and MySQL setup:
```
./setup.sh
```
This will:

-   Set up the MySQL database and user.
    
-   Set up your conda environment as defined in `environment.yml`.
    
-   Load the environment variables from the `.env` file.


### Step 4: Configure the Database (Optional)

After running the `setup.sh` script, you may optionally configure paths and API keys in the `config` table within the database. To do this:

1.  **Access MySQL**:
    
```bash 
sudo mysql -u root -p
```

2.  **Select your database**:
    
```sql
USE your_database_name;
```

3.  **Update the `config` table**:
    

You may modify the following configuration values in the `config` table:

#### Configure Disk Paths

-   **windows_disk_path**: Set the disk path for Windows environments.
    
-   **linux_disk_path**: Set the disk path for Linux environments.
    

Example:

```sql
UPDATE config SET  value='/path/to/windows/disk'  WHERE key='windows_disk_path'; UPDATE config SET  value='/mnt/path/to/linux/disk'  WHERE key='linux_disk_path';
```

#### Configure API URLs

-   **local_llm_url**: Set the local URL for your LLM API.
    

Example:
```sql
UPDATE config SET  value='http://localhost:5000'  WHERE key='local_llm_url';
```
#### Configure External LLM API Keys

-   Set the API keys for external LLM services.
    

Example for an external LLM API key:

```sql
UPDATE config SET  value='sk-antxxxxxxxxxxx123456789'  WHERE key='Claude_API_KEY_API_KEY';
```

### Step 6: Activate Conda Environment


Once everything is set up and configured, you can start using the framework. Run your framework as required.

## How to Run the Framework

After completing the setup, you can run the framework by following these steps:

### Step 1: Add Base Prompts to the `base_prompt` Table

First, you need to insert base prompts into the `base_prompt` table. Each prompt has a **level** (either "beginner" or "expert").

Example query to insert a prompt:

```sql
INSERT INTO `base_prompt` (`prompt`, `level`) VALUES ('Your base prompt text here', 'beginner');
```
Replace `'Your base prompt text here'` with the prompt you want to store.

### Step 2: Create a Job

Next, you need to create a job by inserting a record into the `job` table. This job will specify the parameters for the job execution.

Example query to insert a job:
```sql
INSERT INTO `job` (`id`, `take_in_test_count`, `model_to_use`, `disk_image`, `script_type_need`, `status`, `priority`, `base_prompt_id`, `version`, `cftt_task`, `disk_image_name`)
VALUES (NULL, '10', 'llama3', 'linux_disk_path', 'python', 'queued', '1', '4', '18', 'string_search', NULL);
```

#### Explanation of each field:

-   **take_in_test_count**: The number of test runs for this job (default is 10).
    
-   **model_to_use**: The model to be used for this job (e.g., `llama3`).
    
-   **disk_image**: Path to the disk image for the job. Use `windows_disk_path` or `linux_disk_path`. ( Valid for  CFTT String Search )
    
-   **script_type_need**: The type of code that should be generated. It can be either `python` or `shell`.
    
-   **status**: Set to `queued` to indicate the job is waiting in the queue.
    
-   **priority**: Set a priority (optional; default is 1).
    
-   **base_prompt_id**: The ID of the prompt you want to use. Take the ID from the `base_prompt` table.
    
-   **version**: The version of the job (used to distinguish jobs).
    
-   **cftt_task**: The task type (either `string_search` or `deletedfile_recovery`).
    
-   **disk_image_name**: Set to `NULL` for `string_search`, or specify the disk image name for `deletedfile_recovery`.

### Step 3: Run the Job (**API Handling**)
Once you've created the job, you can run it using the following command:


```bash 
python3 api.py <jobId>
```
Replace `<jobId>` with the actual job ID that you inserted in the `job` table.
This will trigger the job execution based on the configurations you've set in the job record.

### Step 4: Generate Code for the Job (Code Generation Phase)
After creating the job, you can generate the code for this job using the `CodeGenerator.py` script. This will generate the necessary code based on the job parameters.

Run the following command to generate the code:
```bash
python3 CodeGenerator.py <job_id>
```
Replace `<job_id>` with the actual job ID that you inserted into the `job` table.

### Step 5: Execute the Generated Code (Code Execution Phase)
Once the code has been generated, you can manually execute it using the `CodeExecutor.py` script. This will run the generated code based on the job configuration.

Run the following command to execute the code:
```bash
python3 CodeExecutor.py <job_id>
```
Replace `<job_id>` with the actual job ID that you inserted into the `job` table.

### Step 6: Generate Summary and Evaluation (Summary and Evaluation Phase)
After the code has been executed, you can manually generate a summary and evaluation report using the `Summary.py` script.

Run the following command to generate the summary
```bash
python3 Summary.py <job_id>
```
Replace `<job_id>` with the actual job ID.

### Step 7: Retrieve AutoDF Score for the Job
To evaluate the job's performance, you can get the **AutoDF score** from the `test_results` table. Use the following SQL query to retrieve the test results for the specific job:

```sql
SELECT * FROM `test_results` WHERE `job_id` = <job_id>;
```
Replace `<job_id>` with the actual job ID.

Note: You can change the database parameters and code as you need. 
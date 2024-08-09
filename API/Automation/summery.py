import sys
import mysql.connector
from collections import Counter

# Database configuration (replace with your actual database credentials)
DB_HOST = '192.168.1.100'
DB_USER = 'root'
DB_PASSWORD = '19891209'
DB_NAME = 'DFLLM'

base_test_cases = [
    "FT-SS-01",
    "FT-SS-02-a",
    "FT-SS-02-b",
    "FT-SS-02-c",
    "FT-SS-02-d",
    "FT-SS-02-e",
    "FT-SS-03-a",
    "FT-SS-03-b",
    "FT-SS-03-c",
    "FT-SS-04",
    "FT-SS-05",
    "FT-SS-06",
    "FT-SS-07-a1",
    "FT-SS-07-a2",
    "FT-SS-07-b",
    "FT-SS-07-c1",
    "FT-SS-07-c2",
    "FT-SS-07-d",
    "FT-SS-07-e1",
    "FT-SS-07-e2",
    "FT-SS-07-f1",
    "FT-SS-07-f2",
    "FT-SS-07-f3",
    "FT-SS-07-f4",
    "FT-SS-07-g1",
    "FT-SS-07-g2",
    "FT-SS-07-g3",
    "FT-SS-07-g4",
    "FT-SS-07-g5",
    "FT-SS-07-g6",
    "FT-SS-07-g7",
    "FT-SS-07-g8",
    "FT-SS-07-h",
    "FT-SS-08-a1",
    "FT-SS-08-a2",
    "FT-SS-08-a3",
    "FT-SS-08-a4",
    "FT-SS-08-b1",
    "FT-SS-08-b2",
    "FT-SS-08-b3",
    "FT-SS-08-b4",
    "FT-SS-08-c",
    "FT-SS-09-a1",
    "FT-SS-09-a2",
    "FT-SS-09-a3",
    "FT-SS-09-a4",
    "FT-SS-09-a5",
    "FT-SS-09-a6",
    "FT-SS-09-a7",
    "FT-SS-09-a8",
    "FT-SS-09-b",
    "FT-SS-09-c",
    "FT-SS-10-a1",
    "FT-SS-10-a2"
]

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

# Function to fetch and process results for a given job_id and base_test_case
def process_test_results(cursor, job_id, base_test_case):
    try:
        query = """
            SELECT job_id, base_test_case, results, error
            FROM test_results
            WHERE job_id = %s AND base_test_case = %s
        """
        cursor.execute(query, (job_id, base_test_case))
        rows = cursor.fetchall()

        summary_dict = {}

        for row in rows:
            _, _, results, error = row

            if (job_id, base_test_case) not in summary_dict:
                summary_dict[(job_id, base_test_case)] = Counter()

            for line in results.split('\n'):
                if line.endswith('deleted'):
                    summary_dict[(job_id, base_test_case)]['deleted_count'] += 1
                elif line.endswith('active'):
                    summary_dict[(job_id, base_test_case)]['active_count'] += 1
                elif line.endswith('unallocated'):
                    summary_dict[(job_id, base_test_case)]['unallocated_count'] += 1

            # Count the code execution attempts
            if error == '': 
                summary_dict[(job_id, base_test_case)]['code_execution_count'] += 1

            # Count the errors
            if error:
                summary_dict[(job_id, base_test_case)]['errors_count'] += 1

        return summary_dict

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to upsert summary results into the summery_results table
def upsert_summary_results(cursor, summary_dict):
    try:
        upsert_query = """
            INSERT INTO summery_results (job_id, model, base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                active_count = VALUES(active_count),
                deleted_count = VALUES(deleted_count),
                unallocated_count = VALUES(unallocated_count),
                code_execution_count = VALUES(code_execution_count),
                errors_count = VALUES(errors_count)
        """

        for key, counts in summary_dict.items():
            job_id, base_test_case = key
            active_count = counts['active_count']
            deleted_count = counts['deleted_count']
            unallocated_count = counts['unallocated_count']
            code_execution_count = counts['code_execution_count']
            errors_count = counts['errors_count']

            cursor.execute(upsert_query, (job_id, 'your_model', base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count))

    except mysql.connector.Error as err:
        print(f"Error: {err}")

# Main function
def main(job_id):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return

    cursor = conn.cursor()

    for base_test_case in base_test_cases:
        summary_dict = process_test_results(cursor, job_id, base_test_case)
        if summary_dict:
            upsert_summary_results(cursor, summary_dict)

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <job_id>")
    else:
        job_id = sys.argv[1]
        main(job_id)

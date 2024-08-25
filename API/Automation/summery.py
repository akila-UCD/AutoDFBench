import sys
import mysql.connector
from collections import Counter
import os
from difflib import SequenceMatcher

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
            SELECT job_id, base_test_case, testCase, results, error, model
            FROM test_results
            WHERE job_id = %s AND base_test_case like %s
        """
        query_code_exec_count = """SELECT count(*) as code_execution_count FROM `test_results` 
                                WHERE job_id = %s AND base_test_case like %s AND error = '';"""
        cursor.execute(query_code_exec_count, (job_id, f'%{base_test_case}'))
        code_exec_count = cursor.fetchone()[0]

        query_error_count = """SELECT count(*) as error_count FROM `test_results` 
                                WHERE job_id = %s AND base_test_case like %s AND error != '';"""
        cursor.execute(query_error_count, (job_id, f'%{base_test_case}'))
        code_error_count = cursor.fetchone()[0]

        cursor.execute(query, (job_id, f'%{base_test_case}'))
        rows = cursor.fetchall()

        summary_dict = {}

        for index, row in enumerate(rows):
            if index >= 10:  # Stop after processing 10 rows
                break
            _, _, _, results, error, model = row

            if (job_id, base_test_case) not in summary_dict:
                summary_dict[(job_id, base_test_case)] = Counter()

            autopsy_results, all_autopsy_rows = checkGroundTruth(cursor, base_test_case)
            print(f"all_autopsy_rows:{all_autopsy_rows}")

            for line in results.split('\n'):
                # print(f"RESULTS:{results}")
                line2 = line.split(",")[1] if len(line.split(",")) > 2 else ''
                print(f"LINE:{line}")
                
                for any_str_line in all_autopsy_rows:
                    any_similarity = string_similarity(any_str_line, line)
                    if any_similarity == True:
                        summary_dict[(job_id, base_test_case)]['keyword_found_any_location'] += 1

                print(f"SPLITS:{line2}")
                if 'deleted' in line and 'deleted' in autopsy_results:
                    for str_line in autopsy_results['deleted']:
                        similarity = string_similarity(str_line, line2)
                        # deleted_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['deleted_count'] += 1

                elif 'active' in line and 'active' in autopsy_results:
                    for str_line in autopsy_results['active']:
                        similarity = string_similarity(str_line, line2)
                        # active_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['active_count'] += 1

                elif 'unallocated' in line and 'unallocated' in autopsy_results:
                    for str_line in autopsy_results['unallocated']:
                        similarity = string_similarity(str_line, line2)
                        # unallocated_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['unallocated_count'] += 1

        summary_dict[(job_id, base_test_case)]['model'] = model

        summary_dict[(job_id, base_test_case)]['code_execution_count'] = code_exec_count
        summary_dict[(job_id, base_test_case)]['errors_count'] = code_error_count
        summary_dict[(job_id, base_test_case)]['total_code_executions'] = len(rows)

        # Calculate average percentages
        summary_dict[(job_id, base_test_case)]['code_execution_avg_percentage'] = (code_exec_count / len(rows)) * 100 if len(rows) > 0 else 0
        summary_dict[(job_id, base_test_case)]['code_error_avg_percentage'] = (code_error_count / len(rows)) * 100 if len(rows) > 0 else 0

        # summary_dict[(job_id, base_test_case)]['active_similaraty_avg_percentage'] = sum(active_similarity_scores) / len(active_similarity_scores) if active_similarity_scores else 0
        # summary_dict[(job_id, base_test_case)]['deleted_similaraty_avg_percentage'] = sum(deleted_similarity_scores) / len(deleted_similarity_scores) if deleted_similarity_scores else 0
        # summary_dict[(job_id, base_test_case)]['unalocated_similaraty_avg_percentage'] = sum(unallocated_similarity_scores) / len(unallocated_similarity_scores) if unallocated_similarity_scores else 0
        print(summary_dict)

        return summary_dict, model

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def checkGroundTruth(cursor, base_test):
    try:
        query = """
            SELECT file_line, CAST(type AS CHAR) as string_value FROM `autopsy_results` where base_test_case like %s
        """
        cursor.execute(query, (f'%{base_test}',))
        rows = cursor.fetchall()
        result_dict = {}
        lines = []
        for row in rows:
            lines.append(file_line)
            file_line, type_str = row
            if type_str not in result_dict:
                result_dict[type_str] = []  # Initialize a list if the key does not exist
            result_dict[type_str].append(file_line)  # Append the file_line to the list

        # print(result_dict)
        return result_dict, lines
    
    except mysql.connector.Error as err:
        print(f"checkGroundTruth - Error : {err}")
    
# Function to upsert summary results into the summery_results table
def upsert_summary_results(cursor, summary_dict, model):
    try:
        upsert_query = """
            INSERT INTO summery_results (job_id, model, base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count, total_code_executions, code_execution_avg_percentage, code_error_avg_percentage, keyword_found_any_location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                active_count = VALUES(active_count),
                deleted_count = VALUES(deleted_count),
                unallocated_count = VALUES(unallocated_count),
                code_execution_count = VALUES(code_execution_count),
                errors_count = VALUES(errors_count),
                total_code_executions = VALUES(total_code_executions),
                code_execution_avg_percentage = VALUES(code_execution_avg_percentage),
                code_error_avg_percentage = VALUES(code_error_avg_percentage),
                keyword_found_any_location = VALUES(keyword_found_any_location),

        """

        for key, counts in summary_dict.items():
            job_id, base_test_case = key
            active_count = counts['active_count']
            deleted_count = counts['deleted_count']
            unallocated_count = counts['unallocated_count']
            code_execution_count = counts['code_execution_count']
            errors_count = counts['errors_count']
            total_code_executions = counts['total_code_executions']
            code_execution_avg_percentage = counts['code_execution_avg_percentage']
            code_error_avg_percentage = counts['code_error_avg_percentage']
            keyword_found_any_location = counts['keyword_found_any_location']

            cursor.execute(upsert_query, (job_id, model, base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count, total_code_executions, code_execution_avg_percentage, code_error_avg_percentage, keyword_found_any_location))

    except mysql.connector.Error as err:
        print(f"Error: {err}")

import re

def string_similarity(str1, str2):
    # Define the regex pattern to find the 4-digit number followed by '<'
    pattern = r'\b\d{4} <'
    
    # Search for the pattern in both strings
    match1 = re.search(pattern, str1)
    # print(f"{str1, match1}")
    match2 = re.search(pattern, str2)
    
    print(f"{str1 , str2}")

    print(match1.group())
    print(match2.group())
    # Check if both strings have a match and the matches are identical
    if match1 and match2 and match1.group() == match2.group():
        print("match True")
        return True
    else:
        print("match False")
        return False

# Main function
def main(job_id):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return

    cursor = conn.cursor()

    deldupQuery = """DELETE S1 FROM test_results AS S1  
                        INNER JOIN test_results AS S2   
                        WHERE S1.id < S2.id AND S1.testCase = S2.testCase; """

    cursor.execute(deldupQuery)

    for base_test_case in base_test_cases:
        summary_dict, model = process_test_results(cursor, job_id, base_test_case)
        if summary_dict:
            upsert_summary_results(cursor, summary_dict, model)

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <job_id>")
    else:
        job_id = sys.argv[1]
        main(job_id)

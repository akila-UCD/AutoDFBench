import sys
import mysql.connector
from collections import Counter
import os
from difflib import SequenceMatcher
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

specified_column = sys.argv[2] if len(sys.argv) > 2 else None
job_id = sys.argv[1] if len(sys.argv) > 1 else None

# Accessing the database settings from the environment variables
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

base_test_cases_linx = [
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
    "FT-SS-09-b1",
    "FT-SS-09-b2",
    "FT-SS-10-a1",
    "FT-SS-10-a2",
    "FT-SS-10-Hex",
    "FT-SS-09-Stem",
    "FT-SS-09-Stem-steal",
    "FT-SS-09-Stem-city",
    "FT-SS-09-Stem-plan"
]

base_test_cases_windows = [
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
    # "FT-SS-09-b1",
    # "FT-SS-09-b2",
    "FT-SS-09-Frag1",
    "FT-SS-09-Frag2",
    # "FT-SS-09-Lost",
    "FT-SS-10-a1",
    "FT-SS-10-a2",
    "FT-SS-09-Lost-a",
    "FT-SS-09-Lost-b",
    "FT-SS-09-Meta-a",
    "FT-SS-09-Meta-b",
    "FT-SS-09-Stem",
    "FT-SS-10-Hex",
    "FT-SS-09-Stem-steal",
    "FT-SS-09-Stem-city",
    "FT-SS-09-Stem-plan"

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
    
def get_job_details(cursor):
    try:
        query = f"SELECT * FROM `job` WHERE `id` = {job_id}"
        cursor.execute(query)
        for row in cursor:
            print(row)
            return row
    except mysql.connector.Error as err:
        print(f"get_job_details - Error : {err}")

# Function to fetch and process results for a given job_id and base_test_case
def process_test_results(cursor, job_id, base_test_case):
    try:

        job_data = get_job_details(cursor)
        take_in_count = job_data[1]
        query = """
            SELECT job_id, base_test_case, testCase, results, error, model, id
            FROM test_results
            WHERE job_id = %s AND base_test_case like %s LIMIT %s
        """
        query_code_exec_count = """SELECT count(*) as code_execution_count FROM `test_results` 
                                WHERE job_id = %s AND base_test_case like %s AND error = '';"""
        cursor.execute(query_code_exec_count, (job_id, f'%{base_test_case}'))
        code_exec_count = cursor.fetchone()[0]

        query_error_count = """SELECT count(*) as error_count FROM `test_results` 
                                WHERE job_id = %s AND base_test_case like %s AND error != '';"""
        cursor.execute(query_error_count, (job_id, f'%{base_test_case}'))
        code_error_count = cursor.fetchone()[0]

        cursor.execute(query, (job_id, f'%{base_test_case}', take_in_count))
        rows = cursor.fetchall()

        summary_dict = {}

        for index, row in enumerate(rows):
            if index >= 10:  # Stop after processing 10 rows
                break
            _, _, _, results, error, model, id = row
            # print(f"model:{model}")
            print(f"id:{id}")
            # print(f"results:{results}")
            
            
            # Initialize the dictionary entry if it doesn't exist
            if (job_id, base_test_case) not in summary_dict:
                summary_dict[(job_id, base_test_case)] = {
                    'active_count': 0,
                    'deleted_count': 0,
                    'unallocated_count': 0,
                    'keywords_found_any_location': 0,
                    'code_execution_count' :0,
                    'errors_count':0,
                    'total_code_executions':0,
                    'code_execution_avg_percentage':0,
                    'code_error_avg_percentage':0,
                    'model': model
                }

            ground_truth, all_autopsy_rows = checkGroundTruth(cursor, base_test_case)
            # print(f"all_autopsy_rows:{all_autopsy_rows}")

            for line in results.split('\n'):
                # print(f"RESULTS:{results}")
                line2 = line.split(",")[1] if len(line.split(",")) > 2 else ''
                # print(f"LINE:{line}")
                # print(f"LINE2:{line2}")
                # os._exit(1)
               
                for any_str_line in all_autopsy_rows:
                    # print(f"any_str_line: {any_str_line}")
                    # combined_string = ' '.join(line)
                    # print(f"string_line_from_result: {line.strip()}")
                    any_similarity = string_similarity(any_str_line, line.strip())
                    if any_similarity == True:
                        summary_dict[(job_id, base_test_case)]['keywords_found_any_location'] += 1

                # print(f"SPLITS:{line2}")
                if 'deleted' in line:
                    for str_line in ground_truth['deleted']:
                        similarity = string_similarity(str_line, line)
                        # deleted_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['deleted_count'] += 1
                            deleted_query_update_result = f"UPDATE `test_results` SET `deleted_files_hits` = deleted_files_hits+1 WHERE `test_results`.`id` = {id}"
                            print(f"deleted_query_update_result:{deleted_query_update_result}")
                            cursor.execute(deleted_query_update_result)
                            
                elif 'active' in line:
                    for str_line in ground_truth['active']:
                        similarity = string_similarity(str_line, line)
                        # active_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['active_count'] += 1
                            active_query_update_result = f"UPDATE `test_results` SET `active_file_hits` = active_file_hits+1 WHERE `test_results`.`id` = {id}"
                            print(f"active_query_update_result:{active_query_update_result}")
                            cursor.execute(active_query_update_result)

                elif 'unallocated' in line:
                    for str_line in ground_truth['unallocated']:
                        similarity = string_similarity(str_line, line)
                        # unallocated_similarity_scores.append(similarity)
                        if similarity == True:
                            summary_dict[(job_id, base_test_case)]['unallocated_count'] += 1
                            unallocated_query_update_result = f"UPDATE `test_results` SET `unallocated_file_hits` = unallocated_file_hits+1 WHERE `test_results`.`id` = {id}"
                            print(f"unallocated_query_update_result:{unallocated_query_update_result}")
                            cursor.execute(unallocated_query_update_result)

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
        # print(summary_dict)

        # cursor.close()
        return summary_dict, model

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def checkGroundTruth(cursor, base_test):
    try:
        job_data = get_job_details(cursor)
        if job_data[3] == 'windows_disk_path':
            result_type = 'windows'
        else:
            result_type = 'linux'

        query = """
            SELECT file_line, CAST(type AS CHAR) as string_value FROM `ground_truth` where os = %s AND base_test_case like %s
        """
        cursor.execute(query, (result_type,f'%{base_test}',))
        rows = cursor.fetchall()
        result_dict = {}
        result_dict['active'] = []
        result_dict['deleted'] = []
        result_dict['unallocated'] = []
        lines = []
        for row in rows:
            file_line, type_str = row
            lines.append(file_line) 
            if type_str not in result_dict:
                result_dict[type_str] = []  # Initialize a list if the key does not exist
            result_dict[type_str].append(file_line)  # Append the file_line to the list

        # if result_type == 'linux':
        #     result_dict['unallocated'] = []
        print(result_dict)
        return result_dict, lines
    
    except mysql.connector.Error as err:
        print(f"checkGroundTruth - Error : {err}")
    
# Function to upsert summary results into the summery_results table
def upsert_summary_results(cursor, summary_dict, model):
    try:
        upsert_query = """
            INSERT INTO summery_results (job_id, model, base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count, total_code_executions, code_execution_avg_percentage, code_error_avg_percentage, keywords_found_any_location)
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
                keywords_found_any_location = VALUES(keywords_found_any_location)
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
            keywords_found_any_location = counts['keywords_found_any_location']

            cursor.execute(upsert_query, (job_id, model, base_test_case, active_count, deleted_count, unallocated_count, code_execution_count, errors_count, total_code_executions, code_execution_avg_percentage, code_error_avg_percentage, keywords_found_any_location))

    except mysql.connector.Error as err:
        # print(upsert_query)
        print(f"Error: {err}")

import re

def string_similarity(number, str2):
    # Define the regex pattern to find the 4-digit number anywhere in the string
    pattern = rf'\b{re.escape(number)}\b'
    
    # Search for the number in the second string
    match = re.search(pattern, str2)
    
    # Check if the number is found in str2
    if match:
        print("Match True")
        return True
    else:
        # print("Match False")
        return False

def calScoreCal(job_id):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return

    cursor = conn.cursor()
    # job_id = 100
    job_data = get_job_details(cursor)
    if job_data[3] == 'windows_disk_path':
        ops = 'windows'
    else:
        ops = 'linux'

    # q_fetch_results = f"SELECT id,base_test_case,results FROM `test_results` WHERE `job_id` = {job_id} and score_cal_status = 0;"
    q_fetch_results = f"SELECT id,base_test_case,results FROM `test_results` WHERE `id` = 19979"
    cursor.execute(q_fetch_results)
    rows = cursor.fetchall()
    result_ary = {}
    for row in rows:
        r_id = row[0]
        r_base_test_case = extract_test_case(row[1])
        # print(r_base_test_case)
        r_results = row[2]
        
        types = ['active','deleted','unallocated']
        total_tp_count = 0
        total_fp_count = 0
        total_fn_count = 0

        for type in types:
            q_fn = f"SELECT type,file_line FROM `ground_truth` WHERE `base_test_case` LIKE '%{r_base_test_case}%' AND `type` != '{type}' AND `os` = '{ops}' ORDER BY `base_test_case` ASC;"
            cursor.execute(q_fn)
            rows_fn = cursor.fetchall()

        q_fp = f"SELECT type,file_line FROM `ground_truth` WHERE `base_test_case` LIKE '%{r_base_test_case}%' AND `os` = '{ops}' ORDER BY `base_test_case` ASC"
        cursor.execute(q_fp)
        rows_fp = cursor.fetchall()
        fp_ary = []
        for row_fp in rows_fp:
            fp_ary.append(row_fp)
            
        true_positives, false_positives, false_negatives = count_true_false_positives_negatives(r_results, fp_ary, rows_fn,type)

        total_tp_count += true_positives
        total_fp_count += false_positives
        total_fn_count += false_negatives

        print(f"total_tp_count: {total_tp_count}")
        print(f"total_fp_count: {total_fp_count}")
        print(f"total_fn_count: {total_fn_count}")

        if total_tp_count + total_fp_count == 0:
            precision = 0
        else:
            precision = total_tp_count / (total_tp_count + total_fp_count)

        if total_tp_count+total_fn_count == 0:
            recall = 0
        else:
            recall = total_tp_count/ (total_tp_count+total_fn_count)

        if precision + recall == 0:
            f1 = 0
        else:
            f1 =  (2* (precision * recall)) / (precision + recall)
        print(f"precision: {precision}")
        print(f"recall: {recall}")
        print(f"f1: {f1}")

        q_update = f"UPDATE `test_results` SET `TP` = '{total_tp_count}', `FP` = '{total_fp_count}', `FN` = '{total_fn_count}', `precision` = '{precision}', `recall` = '{recall}', `F1` = '{f1}', `score_cal_status` = '1' WHERE `test_results`.`id` = {r_id};"
        cursor.execute(q_update)
        print(f"updated: {r_id}")

    conn.commit()

            


def count_true_false_positives_negatives(text, array, fn_ary,status):

    lines = text.splitlines()

    # First regex pattern to check for status in angle brackets
    pattern_brackets = r"(\d{4})[^0-9]*?<([a-zA-Z]+)>"
    # Second regex pattern to capture the last word if no match is found
    pattern_last_word = r"(\d{4})[^0-9]*?(\w+)\s*$"

    matched_set = set()

    for line in lines:

        matches = re.findall(pattern_brackets, line)
        print(f"Matches with brackets: {matches}") 
        
        if matches:
            matched_set.update((status.lower(), string_id) for string_id, status in matches)
        else:

            matches = re.findall(pattern_last_word, line)
            print(f"Matches with last word: {matches}") 
            
            if matches:
                matched_set.update((last_word.lower(), string_id) for string_id, last_word in matches)

    print("Final Matches:", matched_set) 
    print("status:", matched_set) 
    # os._exit(1)

    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0
    
    # Count true positives, false positives, and false negatives
    for status, str_id in matched_set:
        if (status, str_id) in array:
            true_positive_count += 1
        elif (status, str_id) in fn_ary: 
            false_negative_count += 1
        else: 
            false_positive_count += 1

    # Check for false negatives
    for status, str_id in fn_ary:
        if (status, str_id) in array:
            if (status.lower(), str_id) not in matched_set:
                false_negative_count += 1
    print("true_positive_count:", true_positive_count) 
    os._exit(1)
    return true_positive_count, false_positive_count, false_negative_count
        

    

def extract_test_case(text):

    parts = text.split('_')

    return parts[2]

def cal():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return
    cursor = conn.cursor()
    q_job = f"SELECT id FROM `job` where version = 17;"
    cursor.execute(q_job)
    rows_jobs = cursor.fetchall()
    for job in rows_jobs:
        global job_id
        job_id = job[0]
        calScoreCal(job_id)


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

    job_data = get_job_details(cursor)
    
    resetQuery = f"UPDATE `test_results` SET `active_file_hits` = '0', `deleted_files_hits` = '0', `unallocated_file_hits` = '0' WHERE `job_id` = {job_id}; "
    cursor.execute(resetQuery)
   
    if job_data[3] == 'windows_disk_path':
        base_test_cases = base_test_cases_windows
    else:
        base_test_cases = base_test_cases_linx

    for base_test_case in base_test_cases:
        summary_dict, model = process_test_results(cursor, job_id, base_test_case)
        if summary_dict:
            upsert_summary_results(cursor, summary_dict, model)

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        cal()
        print("Runing cal")
        print("Usage: python script.py <job_id>")
        
    else:
        job_id = sys.argv[1]
        # main(job_id)
        calScoreCal(job_id)

        

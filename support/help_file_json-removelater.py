start_id = 14520
start_num = 0
end_num = 259

base_test_case = "DFR-10/ntfs-10"

base_query = (
    "INSERT INTO `ground_truth` "
    "(`id`, `base_test_case`, `file_line`, `type`, `os`, `cftt_task`, "
    "`file_name`, `size`, `access_time_stamp`, `modify_time_stamp`, "
    "`change_time_stamp`, `deleted_time_stamp`, `f-bks`, `file_hash`, "
    "`carve_types`, `carve_blocks`, `carve_spill`, `gt_file`) "
    "VALUES "
    "({id}, '{base_test_case}', '{file_name}', 'deleted', NULL, "
    "'deleted_file_recovery', '{file_name}', '4096', "
    "NULL, NULL, NULL, '1322276460', "
    "NULL, NULL, NULL, NULL, NULL, NULL);"
)

for i, num in enumerate(range(start_num, end_num + 1), start=0):
    file_name = f"box/xD{num:04d}-4.txt"  # zero-padded to 4 digits
    print(base_query.format(
        id=start_id + i,
        base_test_case=base_test_case,
        file_name=file_name
    ))

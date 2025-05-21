#!/usr/bin/env python3
import subprocess
import os
import re
from datetime import datetime
import time
import pytz

# Configuration
DISK_IMAGE_PATH = "/media/akila/Data/UCD/Phd/DD_IMAGES/DFR/dfr-01/dfr-01-ext.dd"
SECTOR_SIZE = 512  # Default sector size

def get_disk_image_size():
    """Return the size of the disk image in bytes."""
    return os.path.getsize(DISK_IMAGE_PATH)

def run_command(command):
    """Run a shell command and return its output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        # print(f"Error running command: {command}\n{result.stderr}")
        return None
    return result.stdout

def get_partitions():
    """
    Parse the output from mmls to extract partition details.
    Expected mmls output columns:
        Slot | Partition Label | Start | End | Length | Description
    Only partitions with a valid partition label (e.g., "000:000") are processed.
    """
    # print("[*] Getting partitions using mmls...")
    mmls_output = run_command(f"mmls {DISK_IMAGE_PATH}")
    if not mmls_output:
        return []

    partitions = []
    for line in mmls_output.splitlines():
        # print(line)
        # Updated regex to capture all six columns.
        # Example line:
        # 002:  000:000   0000000128   0000016511   0000016384   DOS FAT12 (0x01)
        match = re.match(r'^\s*(\d+):\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+)$', line)
        
        if match:
            slot = match.group(1)
            part_label = match.group(2)
            start = int(match.group(3))
            end = int(match.group(4))
            length = int(match.group(5))
            desc = match.group(6).strip()

            # Only process partitions with a valid partition label like "000:000"
            if not re.match(r'^\d+:\d+$', part_label):
                continue  # Skip entries like "Meta" or "-------"

            partitions.append({
                'slot': slot,
                'partition_label': part_label,
                'start': start,
                'end': end,
                'length': length,
                'desc': desc
            })
    # print(partitions)
    return partitions

def validate_partition(partition):
    """Validate that the partition's byte offset is within the disk image size."""
    byte_offset = partition['start'] * SECTOR_SIZE
    if byte_offset > get_disk_image_size():
        # print(f"[-] Invalid offset for partition {partition['slot']}: Offset ({byte_offset}) exceeds image size.")
        return False
    return True

def parse_metadata(istat_output):
    """
    Parse metadata from istat output.
    Looks for:
        Size:
        Created:
        Accessed:
        Modified:
        Deleted:
    """
    file_name = last_modified_time = last_accessed_time = last_changed_time = created_time = file_size = user_id = group_id = "N/A"
    
    file_name = istat_output[0]
    last_modified_time = istat_output[1]
    last_accessed_time = istat_output[2]
    last_changed_time = istat_output[3]
    created_time = istat_output[4]
    file_size = istat_output[5]
    user_id = istat_output[6]
    group_id = istat_output[7]

    return file_name, last_modified_time, last_accessed_time, last_changed_time, created_time,  file_size, user_id, group_id

def process_partition(partition):
    """Process a valid partition: run fls to list files and extract metadata for each file."""
    byte_offset = partition['start'] * SECTOR_SIZE
    # print(f"[*] Processing Partition {partition['slot']} at byte offset {byte_offset} (Sector {partition['start']})...")

    # Run fls to list active and deleted files. The -r option recurses; -d shows deleted files.
    #-aFlpr will list all the files > file_type inode file_name mod_time acc_time chg_time cre_time size uid gid
    #-d     Display deleted entries only
    #-u     Display undeleted entries only
    fls_cmd = f"fls -dmaFlr -o {partition['start']} {DISK_IMAGE_PATH}"
    print(fls_cmd)
    fls_output = run_command(fls_cmd)
    # print(fls_cmd)
    if not fls_output:
        return

    # Each fls output line should have an inode and a file name.
    for line in fls_output.splitlines():
        # Typical fls line: "12345: filename" (may have extra spaces)
        elemnts = line.split("|")
        print(elemnts)
        
        # match = re.match(r'^.*?(\d+):\s+(.+)$', line)
        # print(match)
        if 'deleted' in elemnts[1]:
            inode = elemnts[2]
            filename = elemnts[1]
            file_size = elemnts[6]
            created_time = elemnts[7] 
            last_accessed_time = elemnts[9] 
            last_modified_time = elemnts[8]
            last_changed_time = elemnts[10]
            # print(elemnts)
            istat_output = split_keep_timestamps(filename)
            # print(istat_output)
            # # Get file metadata using istat for this inode
            istat_cmd = f"istat -z GMT -o {partition['start']} {DISK_IMAGE_PATH} {inode}"
            # print(istat_cmd)
            istat_output = run_command(istat_cmd)
            deleted_time = ''
            # print(istat_output)
            if istat_output:
                deleted_time = convert_to_epoch(parse_inode_output(istat_output))
                # print(deleted_time)
            # os._exit(1)
            # if istat_output:
            # filename, last_modified_time, last_accessed_time, last_changed_time, created_time,  file_size, user_id, group_id = parse_metadata(istat_output)
            # Print the file information in the required format:
            # filename,file_size,created_timestamp,access_timestamp,modified_timestamp,deleted_timestamp
            print(f"{filename}, {file_size}, {created_time}, {last_accessed_time}, {last_modified_time}, {last_changed_time}, {deleted_time}")

def parse_inode_output(output):
    # Initialize variables to store the extracted values
    deleted = None

    # Split the output into lines
    lines = output.splitlines()

    # Iterate through each line to find the required fields
    for line in lines:
        if line and line.startswith("Deleted:"):
            deleted = line.split(":", 1)[1].strip()
            deleted = datetime.strptime(deleted, "%Y-%m-%d %H:%M:%S (GMT)")

    # Return the extracted values as an array
    return deleted


def split_keep_timestamps(line):
    """
    Splits the input line by spaces but keeps timestamps as single attributes.
    
    Args:
        line (str): The input line containing timestamps and other fields.
    
    Returns:
        list: A list of fields, with timestamps kept intact.
    """
    # Regex to match timestamps in the format "YYYY-MM-DD HH:MM:SS (UTC)"
    timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \(\w+\)'
    
    # Find all timestamps in the line
    timestamps = re.findall(timestamp_pattern, line)
    
    # Replace timestamps with a placeholder to simplify splitting
    placeholder = "TIMESTAMP_PLACEHOLDER"
    for timestamp in timestamps:
        line = line.replace(timestamp, placeholder)
    
    # Split the line by spaces
    parts = line.split()
    
    # Replace placeholders with the original timestamps
    result = []
    timestamp_index = 0
    for part in parts:
        if part == placeholder:
            # Parse the timestamp and convert to epoch time
            timestamp_str = timestamps[timestamp_index]
            print(timestamp_str)
            # Extract the datetime part (without timezone)
            datetime_str = timestamp_str.split(' (')[0]
            
            # Handle invalid dates like '0000-00-00 00:00:00'
            if datetime_str == '0000-00-00 00:00:00':
                epoch_time = 0  # Default value for invalid dates
            else:
                try:
                    # Parse the datetime string
                    dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    # Convert to epoch time
                    epoch_time = int(time.mktime(dt.timetuple()))
                except ValueError:
                    # Handle other potential parsing errors
                    epoch_time = 0  # Default value for invalid dates
            
            result.append(str(epoch_time))
            timestamp_index += 1
        else:
            result.append(part)

    return result

def convert_to_epoch(timestamp_str):
    # Map timezone abbreviations to pytz timezones
    timezone_map = {
        "GMT": "UTC",
        "IST": "Asia/Kolkata",
        "UTC": "UTC",
        "EDT": "America/New_York",  # Eastern Daylight Time
        "EST": "America/New_York",  # Eastern Standard Time
        "PDT": "America/Los_Angeles",  # Pacific Daylight Time
        "PST": "America/Los_Angeles",  # Pacific Standard Time
        "CST": "America/Chicago",  # Central Standard Time
        "CDT": "America/Chicago",  # Central Daylight Time
        "MST": "America/Denver",  # Mountain Standard Time
        "MDT": "America/Denver",  # Mountain Daylight Time
    }
    
    try:
        # Handle invalid date "0000-00-00" by returning 0 (Unix epoch reference)
        if timestamp_str and timestamp_str.startswith("0000-00-00"):
            return 0
        
        # Handle timestamps with named timezones
        match = re.match(r"(\w{3}) (\w{3}) (\d{1,2}) (\d{2}):(\d{2}):(\d{2}) (\w{3}) (\d{4})", timestamp_str)
        if match:
            day_abbr, month_abbr, day, hour, minute, second, tz_abbr, year = match.groups()
            dt_str = f"{year} {month_abbr} {day} {hour}:{minute}:{second}"
            dt = datetime.strptime(dt_str, "%Y %b %d %H:%M:%S")
            
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                dt = tz.localize(dt)
            else:
                raise ValueError(f"Unknown timezone abbreviation: {tz_abbr}")
        else:
            # Handle numeric timezones
            timestamp_str = re.sub(r"(\.\d{6})\d+", r"\1", timestamp_str)  # Trim nanoseconds
            if "." in timestamp_str:
                format_str = "%Y-%m-%d %H:%M:%S.%f %z"
            else:
                format_str = "%Y-%m-%d %H:%M:%S %z"
            dt = datetime.strptime(timestamp_str, format_str)
        
        # Convert to epoch timestamp
        epoch_time = dt.timestamp()
        return int(epoch_time)
    except Exception as e:
        print(f"Error processing timestamp: {e}")
        return None
    

def main():
    partitions = get_partitions()
    if not partitions:
        # print("[-] No valid partitions found.")
        return

    for partition in partitions:
        if validate_partition(partition):
            process_partition(partition)
        else:
            print ('')
            # print(f"[-] Skipping partition {partition['slot']} due to invalid offset.")

if __name__ == "__main__":
    main()

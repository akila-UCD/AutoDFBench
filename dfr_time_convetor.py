from datetime import datetime
import re
import pytz

def convert_to_epoch(timestamp_str):
    # Map timezone abbreviations to offsets
    timezone_map = {
        "(GMT)": "+0000",
        "(IST)": "+0430",
        "(UTC)": "+0000"
    }
    
    # Replace timezone abbreviations with corresponding offsets
    for tz, offset in timezone_map.items():
        timestamp_str = timestamp_str.replace(tz, offset)
    
    # Handle invalid date "0000-00-00" by returning 0 (Unix epoch reference)
    if timestamp_str.startswith("0000-00-00"):
        return 0
    
    # Trim nanoseconds to microseconds if present
    timestamp_str = re.sub(r"(\.\d{6})\d+", r"\1", timestamp_str)
    
    # Determine the correct format based on presence of fractional seconds
    if "." in timestamp_str:
        format_str = "%Y-%m-%d %H:%M:%S.%f %z"
    else:
        format_str = "%Y-%m-%d %H:%M:%S %z"
    
    # Parse the timestamp string into a datetime object
    dt = datetime.strptime(timestamp_str, format_str)
    
    # Convert to epoch timestamp
    epoch_time = dt.timestamp()
    
    return int(epoch_time)

# Example usage
time_str = "2011-10-09 13:10:20.660434905 -0400"
print(convert_to_epoch(time_str))

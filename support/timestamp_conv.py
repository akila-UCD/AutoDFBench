import sys
from datetime import datetime
import re
import pytz
import time

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
        if timestamp_str.startswith("0000-00-00"):
            return 0
        
        # Branch 1: Format "YYYY-MM-DD HH:MM:SS (TZ)"
        m = re.match(r"^(.*\d{2}:\d{2}:\d{2}) \((\w+)\)$", timestamp_str)
        if m:
            base_time = m.group(1)  # e.g., "2011-10-09 18:13:00"
            tz_abbr = m.group(2)    # e.g., "IST"
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                dt_naive = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S")
                dt = tz.localize(dt_naive)
                # Now we can return the epoch
                return int(dt.timestamp())
            else:
                raise ValueError(f"Unknown timezone abbreviation: {tz_abbr}")
        
        # Branch 2: Format "Day Abbr Month Abbr D HH:MM:SS TZ YYYY"
        # Example: "Sun Oct 9 13:12:59 EDT 2011"
        m2 = re.match(r"^(\w{3}) (\w{3}) (\d{1,2}) (\d{2}:\d{2}:\d{2}) (\w{3}) (\d{4})$", timestamp_str)
        if m2:
            day_abbr, month_abbr, day, time_part, tz_abbr, year = m2.groups()
            dt_str = f"{year} {month_abbr} {day} {time_part}"
            dt_naive = datetime.strptime(dt_str, "%Y %b %d %H:%M:%S")
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                dt = tz.localize(dt_naive)
                return int(dt.timestamp())
            else:
                raise ValueError(f"Unknown timezone abbreviation: {tz_abbr}")
        
        # Branch 3: Numeric timezone formats (with or without fractional seconds)
        # Trim nanoseconds to microseconds if present
        timestamp_str = re.sub(r"(\.\d{6})\d+", r"\1", timestamp_str)
        if "." in timestamp_str:
            format_str = "%Y-%m-%d %H:%M:%S.%f %z"
        else:
            format_str = "%Y-%m-%d %H:%M:%S %z"
        dt = datetime.strptime(timestamp_str, format_str)
        return int(dt.timestamp())
    
    except Exception as e:
        print(f"Error processing timestamp: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert_to_timestamp.py 'YYYY-MM-DD HH:MM:SS.sssssssss ±HHMM'")
    else:
        time_str = sys.argv[1]
        timestamp = convert_to_epoch(time_str)
        print(f"Timestamp: {timestamp}")
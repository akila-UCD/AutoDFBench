# autodfbench/utils/form_parser.py
"""
Form parser module for handling multipart form data
"""

def parse_multipart_form_data(headers, data):
    content_type = headers.get('content-type', '')
    if 'multipart/form-data' not in content_type:
        return None, None

    # Extract boundary
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part.split('=', 1)[1].strip('"')
            break

    if not boundary:
        return None, None

    boundary = boundary.encode('utf-8')
    form_data = {}
    files = {}

    # Split by boundary
    parts = data.split(b'--' + boundary)

    for part in parts[1:-1]:  # Skip first empty part and last closing part
        if not part.strip():
            continue

        # Split headers and body
        if b'\r\n\r\n' in part:
            headers_section, body = part.split(b'\r\n\r\n', 1)
        else:
            continue

        headers_section = headers_section.decode('utf-8', errors='ignore')

        # Parse Content-Disposition header
        name = None
        filename = None
        for line in headers_section.split('\r\n'):
            if line.startswith('Content-Disposition:'):
                if 'name="' in line:
                    start = line.find('name="') + 6
                    end = line.find('"', start)
                    name = line[start:end]

                if 'filename="' in line:
                    start = line.find('filename="') + 10
                    end = line.find('"', start)
                    filename = line[start:end]
                break

        if not name:
            continue

        # Remove trailing boundary markers
        body = body.rstrip(b'\r\n')

        if filename:  # It's a file
            if name not in files:
                files[name] = []
            files[name].append({
                'filename': filename,
                'content': body
            })
        else:  # It's a regular form field
            form_data[name] = body.decode('utf-8', errors='ignore')

    return form_data, files

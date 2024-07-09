import json
import lzma
import os
from datetime import datetime, timedelta

import msgpack


def read_compressed_data(filename):
    file_size = os.path.getsize(filename)
    data_points = 0
    first_timestamp = None
    last_timestamp = None
    first_data = None
    last_data = None

    with lzma.open(filename, 'rb') as f:
        unpacker = msgpack.Unpacker(f, raw=False)
        for unpacked_data in unpacker:
            data_points += 1
            current_timestamp = datetime.fromisoformat(unpacked_data['timestamp'])
            
            if first_timestamp is None:
                first_timestamp = current_timestamp
                first_data = unpacked_data
            last_timestamp = current_timestamp
            last_data = unpacked_data

            yield unpacked_data

    # Calculate statistics
    if first_timestamp and last_timestamp:
        duration = (last_timestamp - first_timestamp).total_seconds() / 3600  # in hours
        if duration > 0:
            growth_rate = file_size / duration  # bytes per hour
            predicted_size_24h = growth_rate * 24 / (1024 * 1024)  # Convert to MB

            print(f"Current file size: {file_size / (1024 * 1024):.2f} MB")
            print(f"Number of data points: {data_points}")
            print(f"Duration: {duration:.2f} hours")
            print(f"Growth rate: {growth_rate / (1024 * 1024):.2f} MB/hour")
            print(f"Predicted size after 24 hours: {predicted_size_24h:.2f} MB")

            print("\nFirst data point:")
            print(json.dumps(first_data, indent=2))

            print("\nLast data point:")
            print(json.dumps(last_data, indent=2))
        else:
            print("Not enough data to make a prediction.")
    else:
        print("No data found in the file.")

# Usage
filename = 'ws_data/price_data.xz'
for data in read_compressed_data(filename):
    # Process data as needed
    pass  # Remove this line if you want to process the data
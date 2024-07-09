import gzip
import json


def read_compressed_data(filename):
    with gzip.open(filename, 'rt') as f:
        for line in f:
            yield json.loads(line)

def process_data(data):
    # This is a sample processing function. Modify as needed.
    timestamp = data.get('timestamp')
    price = data.get('price')
    print(f"Timestamp: {timestamp}, Price: {price}")

# Usage
if __name__ == "__main__":
    filename = 'ws_data/price_data.json.gz'
    try:
        for data in read_compressed_data(filename):
            process_data(data)
    except FileNotFoundError:
        print(f"File not found: {filename}")
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
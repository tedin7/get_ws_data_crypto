from prometheus_client import start_http_server, Counter, Gauge
import psutil
import time
import os

# Metrics
WS_DATA_FILES = Gauge('ws_data_files', 'Number of data files')
MEMORY_USAGE = Gauge('getws_memory_mb', 'Memory usage in MB')
CPU_USAGE = Gauge('getws_cpu_percent', 'CPU usage percentage')

def get_process_metrics():
    for proc in psutil.process_iter(['pid', 'name']):
        if 'python' in proc.info['name']:
            try:
                p = psutil.Process(proc.info['pid'])
                if 'main.py' in ' '.join(p.cmdline()):
                    MEMORY_USAGE.set(p.memory_info().rss / 1024 / 1024)
                    CPU_USAGE.set(p.cpu_percent())
            except:
                pass

def count_data_files():
    try:
        data_path = '/home/getws/get_ws_data_crypto/ws_data'
        files = [f for f in os.listdir(data_path) if f.endswith('.jsonl')]
        count = len(files)
        WS_DATA_FILES.set(count)
        print(f"Found {count} files in {data_path}")  # Debug logging
    except Exception as e:
        print(f"Error counting files: {str(e)}")
        WS_DATA_FILES.set(0)
if __name__ == '__main__':
    start_http_server(9091)
    while True:
        get_process_metrics()
        count_data_files()
        time.sleep(15)

import os
import requests
import threading
from queue import Queue
import time
from tqdm import tqdm
import psutil

# Download settings
url = "https://www.chmlfrp.cn/dw/ChmlFrp-0.51.2_240715_windows_amd64.zip"
filename = "ChmlFrp-0.51.2_240715_windows_amd64.zip"
chunk_size = 1024 * 1024  # 1MB chunks


class DownloadThread(threading.Thread):
    def __init__(self, chunk_queue: Queue, url: str, progress_bar: tqdm):
        super().__init__(daemon=True)
        self.chunk_queue = chunk_queue
        self.url = url
        self.progress_bar = progress_bar

    def run(self):
        while True:
            chunk_info = self.chunk_queue.get()
            if chunk_info is None:
                break
            chunk_id, start_byte, end_byte = chunk_info
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84",
                "Range": f"bytes={start_byte}-{end_byte}"
            }
            response = requests.get(self.url, headers=headers)
            with open(f"files/{chunk_id}.tmp", "wb") as f:
                f.write(response.content)
            self.progress_bar.update(end_byte - start_byte + 1)
            self.chunk_queue.task_done()


def get_file_size(url: str) -> int:
    response = requests.head(url)
    return int(response.headers.get('Content-Length', 0))


def create_chunk_queue(file_size: int) -> Queue:
    chunk_queue = Queue()
    start_byte = 0
    chunk_id = 0
    while start_byte < file_size:
        end_byte = min(start_byte + chunk_size - 1, file_size - 1)
        chunk_queue.put((chunk_id, start_byte, end_byte))
        start_byte = end_byte + 1
        chunk_id += 1
    return chunk_queue


def create_threads(chunk_queue: Queue, url: str, progress_bar: tqdm) -> list:
    thread_count = 8
    threads = []
    for _ in range(thread_count):
        thread = DownloadThread(chunk_queue, url, progress_bar)
        thread.start()
        threads.append(thread)
    return threads


def composite_file(total_chunks: int):
    if os.path.exists(filename):
        os.remove(filename)
    with open(filename, "ab") as f:
        for i in range(total_chunks):
            chunk_file = f"files/{i}.tmp"
            if os.path.exists(chunk_file):
                with open(chunk_file, "rb") as chunk:
                    f.write(chunk.read())
                os.remove(chunk_file)


def main():
    if not os.path.exists("files"):
        os.makedirs("files")

    file_size = get_file_size(url)
    if file_size == 0:
        print("Unable to determine file size. Aborting download.")
        return

    chunk_queue = create_chunk_queue(file_size)
    total_chunks = chunk_queue.qsize()

    with tqdm(total=file_size, unit='B', unit_scale=True, desc=filename) as progress_bar:
        threads = create_threads(chunk_queue, url, progress_bar)

        # Add sentinel values to stop threads
        for _ in range(len(threads)):
            chunk_queue.put(None)

        # Wait for all chunks to be downloaded
        chunk_queue.join()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

    composite_file(total_chunks)
    print(f"\nDownload completed: {filename}")


if __name__ == '__main__':
    main()
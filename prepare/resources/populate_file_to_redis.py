import os
import redis

current_directory = os.path.dirname(os.path.realpath(__file__))


def store_files_in_redis(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            with open(file_path, 'rb') as file_content:
                key = file_path.split("/")[-1]
                redis_client.set(key, file_content.read())
                print(f'Stored {key} in Redis')


if __name__ == '__main__':
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    store_files_in_redis(current_directory)
    print("All files have been stored in Redis.")

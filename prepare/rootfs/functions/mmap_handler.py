import mmap
import time


def lambda_handler(event, context):
    ts1 = time.time()
    size = int(event['size'])
    mm = mmap.mmap(-1, 1024 * 1024 * size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
    for i in range(0, 1024 * 1024 * 512, 4096):
        mm[i] = 1
    mm.close()
    ts2 = time.time()
    return [ts1, ts2]


if __name__ == '__main__':
    print(lambda_handler(None, None))

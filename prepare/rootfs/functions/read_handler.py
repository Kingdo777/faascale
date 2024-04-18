import time


def lambda_handler(event, context):
    ts1 = time.time()
    l = [1] * (64 * 1024 * 1024)
    for i in range(0, len(l), 512):
        a = l[i]
    ts2 = time.time()
    return [ts1, ts2]


if __name__ == '__main__':
    print(lambda_handler(None, None))

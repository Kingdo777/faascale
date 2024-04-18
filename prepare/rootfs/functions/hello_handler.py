import time


def lambda_handler(event, context):
    ts = time.time()
    return [ts, ts]


if __name__ == '__main__':
    print(lambda_handler(None, None))

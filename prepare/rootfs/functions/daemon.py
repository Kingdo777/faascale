import json
import multiprocessing
import os
import random
import signal
import string
import subprocess
import tempfile

from flask import Flask, request

app = Flask(__name__)

import time
import redis
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)
MEMINFO = False
ENABLE_TCPDUMP = False

global_queue = multiprocessing.Queue()
characters = string.ascii_letters + string.digits

# DUMPPATH = '/dev/shm/dump'
if ENABLE_TCPDUMP:
    dumpfile = open('/dev/shm/dump', 'w+')
    tcpdump_proc = subprocess.Popen(['tcpdump', '--immediate-mode', '-l', '-i', 'any'], bufsize=0, shell=True,
                                    stdout=dumpfile, stderr=dumpfile, text=True)


def invoke_function(*args):
    funcname, request_args, context = args
    if funcname == 'hello':
        ts = time.time()
        return [ts, ts]
    if funcname == 'read':
        import read_handler
        return read_handler.lambda_handler(request_args, context)
    if funcname == 'image':
        import image_processing
        return image_processing.lambda_handler(request_args, context)
    if funcname == 'mmap':
        import mmap_handler
        return mmap_handler.lambda_handler(request_args, context)
    if funcname == 'json':
        import json_dumps_loads
        return json_dumps_loads.lambda_handler(request_args, context)
    if funcname == 'ffmpeg':
        import ffmpeg_lambda_handler
        return ffmpeg_lambda_handler.lambda_handler(request_args, context)
    if funcname == 'chameleon':
        import chameleon_handler
        return chameleon_handler.lambda_handler(request_args, context)
    if funcname == 'matmul':
        import matmul_lambda_handler
        return matmul_lambda_handler.lambda_handler(request_args, context)
    if funcname == 'pyaes':
        import pyaes_lambda_handler
        return pyaes_lambda_handler.lambda_handler(request_args, context)
    if funcname == 'compression':
        import compression_handler
        return compression_handler.lambda_handler(request_args, context)
    if funcname == 'recognition':
        import recognition_handler
        return recognition_handler.lambda_handler(request_args, context)
    if funcname == 'pagerank':
        import pagerank_handler
        return pagerank_handler.lambda_handler(request_args, context)
    if funcname == 'exec':
        ts1 = time.time()
        exec(request_args['script'], globals())
        ts2 = time.time()
        return [ts1, ts2]
    if funcname == 'run':
        ts1 = time.time()
        subprocess.run(request_args['args'], shell=True, check=True)
        ts2 = time.time()
        return [ts1, ts2]
    raise RuntimeError('unknown function')


def function(*args):
    global global_queue
    funcname, hostname, password, funcmem, request_args = args
    r = redis.Redis(host=hostname, port=6379, db=0, password=password)

    if funcname.endswith('-faascale'):
        type_ = "faascale"
    elif funcname.endswith('-balloon'):
        type_ = 'balloon'
    else:
        return invoke_function(funcname, request_args, {'r': r})

    pipe_path = tempfile.mktemp()
    os.mkfifo(pipe_path)
    global_queue.put((type_, pipe_path))
    with open(pipe_path, 'w') as f:
        f.write(json.dumps({
            "funcname": funcname[0:(len(type_) + 1) * -1],
            "request_args": request_args,
            "funcmem": funcmem,
            "context": {'hostname': hostname, 'password': password}
        }))
    with open(pipe_path, 'r') as f:
        data = f.read()
        print(data)
        result = json.loads(data)["result"]
    os.remove(pipe_path)
    return result


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/invoke', methods=['POST'])
def invoke():
    funcname = request.args['function']
    redishost = request.args['redishost']
    redispasswd = request.args['redispasswd']
    funcmem = request.args['funcmem']

    starttime = time.time()
    result = function(funcname, redishost, redispasswd, funcmem, request.json)
    finishtime = time.time()
    return 'read %f\nprocess %f\nwrite %f' % (result[0] - starttime, result[1] - result[0], finishtime - result[1])


@app.route('/logs')
def logs():
    ret, output = subprocess.getstatusoutput('journalctl')
    return output


@app.route('/tcpdump')
def tcpdump():
    dumpfile = open('/dev/shm/dump', 'r')
    contents = dumpfile.read()
    return contents


@app.route('/dmesg')
def dmesg():
    ret, output = subprocess.getstatusoutput('dmesg')
    return output


@app.route('/makenoise')
def syslog():
    size_s = request.args['size']
    size = 1024 * 1024 * int(size_s)
    l = [1] * size
    return "OK"


def zygote_balloon_handler(pipe_path):
    with open(pipe_path, 'r') as f:
        data = json.loads(f.read())
        funcname = data['funcname']
        request_args = data['request_args']
        context = data['context']
    r = redis.Redis(host=context['hostname'], port=6379, db=0, password=context['password'])
    result = invoke_function(funcname, request_args, {'r': r})
    with open(pipe_path, 'w') as f:
        f.write(json.dumps({"result": result}))


def zygote_faascale_handler(pipe_path):
    with open(pipe_path, 'r') as f:
        data = json.loads(f.read())
        funcname = data['funcname']
        request_args = data['request_args']
        context = data['context']
        funcmem = data['funcmem']
    r = redis.Redis(host=context['hostname'], port=6379, db=0, password=context['password'])
    random_string = ''.join(random.choices(characters, k=8))
    cgroup_path = '/sys/fs/cgroup/memory/faascale/%s' % random_string
    os.makedirs(cgroup_path, exist_ok=False)
    size = "{}M".format(funcmem)
    with open(os.path.join(cgroup_path, 'memory.faascale.size'), 'w') as f:
        f.write(size)

    read_, write_ = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_)
        pid = os.getpid()
        with open(os.path.join(cgroup_path, 'cgroup.procs'), 'w') as f:
            f.write(str(pid))
        result = invoke_function(funcname, request_args, {'r': r})
        os.write(write_, json.dumps(result).encode())
        os.close(write_)
        time.sleep(10)
    os.close(write_)
    result = os.read(read_, 1024)
    with open(pipe_path, 'w') as f:
        f.write(json.dumps({"result": json.loads(result)}))
    os.close(read_)
    os.kill(pid, signal.SIGTERM)
    os.wait()
    os.rmdir(cgroup_path)


def zygote_function():
    global global_queue
    import hello_handler
    import read_handler
    import image_processing
    import mmap_handler
    import json_dumps_loads
    import ffmpeg_lambda_handler
    import chameleon_handler
    import matmul_lambda_handler
    import pyaes_lambda_handler
    import compression_handler
    import recognition_handler
    import pagerank_handler

    while True:
        try:
            type_, pipe_path = global_queue.get()
        except Exception as e:
            print(e)
            return None
        if type_ == 'balloon':
            p = multiprocessing.Process(target=zygote_balloon_handler,
                                        args=(pipe_path,),
                                        daemon=True)
            p.start()
        elif type_ == 'faascale':
            p = multiprocessing.Process(target=zygote_faascale_handler,
                                        args=(pipe_path,))
            p.start()

        else:
            raise RuntimeError('unknown type, only balloon and faascale supported')


if __name__ == '__main__':
    zygote_proc = multiprocessing.Process(target=zygote_function, args=())
    zygote_proc.start()

    app.run(host="0.0.0.0")
    zygote_proc.terminate()
    global_queue.close()

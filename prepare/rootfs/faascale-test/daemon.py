import json
import os
from flask import Flask, request
import time

app = Flask(__name__)


@app.route('/')
def invoke():
    size_mib = int(request.args['size'])

    return create_faascale_cgroup(size_mib)


def create_faascale_cgroup(size_mib):
    size = "{}M".format(size_mib)

    scale_up_uses = []
    scale_down_uses = []
    for i in range(100):
        start1 = time.time()
        with open(os.path.join(cgroup_path, 'memory.faascale.size'), 'w') as f:
            f.write(size)

        start2 = time.time()
        with open(os.path.join(cgroup_path, 'memory.faascale.free'), 'w') as f:
            f.write("1")
        end = time.time()
        scale_up_uses.append((start2 - start1) * 1000)
        scale_down_uses.append((end - start2) * 1000)

    return json.dumps({'scale_up_uses': sum(scale_up_uses) / len(scale_up_uses),
                       'scale_down_uses': sum(scale_down_uses) / len(scale_down_uses)})


if __name__ == '__main__':
    cgroup_path = '/sys/fs/cgroup/memory/faascale'
    os.makedirs(cgroup_path, exist_ok=False)
    app.run(host="0.0.0.0")
    os.rmdir(cgroup_path)

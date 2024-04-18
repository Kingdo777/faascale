import asyncio
import json
import time
import os

from flask import Flask, request

from qemu.qmp import QMPClient


async def current_balloon_size():
    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')
    origin_size = (await qmp.execute('query-balloon'))['actual']
    await qmp.disconnect()
    return origin_size


async def change_balloon(target):
    # command docs: https://qemu-project.gitlab.io/qemu/interop/qemu-qmp-ref.html
    # qmp docs:https://qemu.readthedocs.io/projects/python-qemu-qmp/en/latest/main.html
    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')

    target_byte = target * 1024 * 1024

    origin_size = int((await qmp.execute('query-balloon'))['actual'] / 1024 / 1024)

    start_time = time.time()
    res = await qmp.execute('balloon', {"value": target_byte})
    assert len(res) == 0
    while True:
        res = await qmp.execute('query-balloon')
        current_size = int(res['actual'])
        if current_size == target_byte:
            # time.sleep(0.01)  # sleep 10ms
            break
    end_time = time.time()
    print("scale balloon {}MB to {}MB uses {:.1f}ms".format(origin_size, target, (end_time - start_time) * 1000))

    await qmp.disconnect()


async def current_virtio_mem_block_size():
    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')
    size = await qmp.execute('qom-get', {"path": "vm0", "property": "block-size"})
    await qmp.disconnect()
    return size


async def current_virtio_mem_size():
    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')
    size = await qmp.execute('qom-get', {"path": "vm0", "property": "size"})
    await qmp.disconnect()
    return size


async def change_virtio_mem(requested_size):
    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')

    requested_size_byte = requested_size * 1024 * 1024

    origin_size = int(await qmp.execute('qom-get', {"path": "vm0", "property": "size"}) / 1024 / 1024)

    start_time = time.time()
    res = await qmp.execute('qom-set', {"path": "vm0", "property": "requested-size", "value": requested_size_byte})
    assert len(res) == 0
    while True:
        current_size = int(await qmp.execute('qom-get', {"path": "vm0", "property": "size"}))
        if current_size == requested_size_byte:
            # time.sleep(0.1)  # sleep 100ms
            break
    end_time = time.time()
    print(
        "change virtio_mem {}MB to {}MB uses {:.1f}ms".format(origin_size, requested_size,
                                                              (end_time - start_time) * 1000))

    await qmp.disconnect()


app = Flask(__name__)


@app.route('/')
def hello_world():
    target = os.environ.get('TARGET', 'World')
    return 'Hello {}!\n'.format(target)


@app.route('/change_balloon_to')
def change_to():
    start_time = time.time()
    asyncio.run(change_balloon(target=int(request.args.get('value'))))
    use_time = (time.time() - start_time) * 1000
    print("change_to req use {:.1f}ms".format(use_time))
    return json.dumps({'use_time': use_time})


@app.route('/current_balloon_size')
def current_size():
    start_time = time.time()
    current = asyncio.run(current_balloon_size())
    use_time = (time.time() - start_time) * 1000
    print("current_size req use {:.1f}ms".format(use_time))
    return json.dumps({'current_size': current, 'use_time': use_time})


@app.route('/current_virtio_mem_size')
def current_virtio_size():
    start_time = time.time()
    current = asyncio.run(current_virtio_mem_size())
    use_time = (time.time() - start_time) * 1000
    print("current_virtio_mem_size req use {:.1f}ms".format(use_time))
    return json.dumps({'block_size': "{}MB".format(asyncio.run(current_virtio_mem_block_size()) / 1024 / 1024),
                       'size': "{}MB".format(current / 1024 / 1024),
                       'use_time': use_time})


@app.route('/change_virtio_mem_to')
def change_virtio_to():
    start_time = time.time()
    value = int(request.args.get('value'))
    asyncio.run(change_virtio_mem(requested_size=value))
    use_time = (time.time() - start_time) * 1000
    print("change_virtio_mem_to req use {:.1f}ms".format(use_time))
    return json.dumps({'use_time': use_time})


async def test():
    # memaddr: 0x140000000
    # node: 0
    # requested - size: 0
    # size: 0
    # max - size: 4294967296
    # block - size: 2097152
    # memdev: / objects / vmem0

    qmp = QMPClient('my-vm-nickname')
    await qmp.connect('/tmp/qmp.sock')
    memaddr = await qmp.execute('qom-get', {"path": "vm0", "property": "memaddr"})
    size = await qmp.execute('qom-get', {"path": "vm0", "property": "size"})
    print(hex(memaddr))
    print(type(size))


if __name__ == "__main__":
    # asyncio.run(test())
    # print(asyncio.run(current_virtio_mem_size()))
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8081)))

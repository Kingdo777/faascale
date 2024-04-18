#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import requests
import httpx


def test_balloon(sizes: list, socket_location: str):
    for size_ in sizes:
        for size in [size_, 0]:
            start = time.time()
            # curl --unix-socket $socket_location -i \
            #     -X PATCH 'http://localhost/balloon' \
            #     -H 'Accept: application/json' \
            #     -H 'Content-Type: application/json' \
            #     -d "{
            #         \"amount_mib\": $amount_mib, \
            #         \"stats_polling_interval_s\": $polling_interval \
            #     }"

            client = httpx.Client(transport=httpx.HTTPTransport(uds=socket_location))
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            data = {
                "amount_mib": size,
            }
            resp = client.patch("http://localhost/balloon", headers=headers, json=data)
            if resp.status_code != 204:
                raise "balloon statistics error: " + resp.text

            # curl --unix-socket $socket_location -i \
            #     -X GET 'http://localhost/balloon/statistics' \
            #     -H 'Accept: application/json'

            headers = {
                'Accept': 'application/json'
            }
            for i in range(1000):
                resp = client.get("http://localhost/balloon/statistics", headers=headers)
                if resp.status_code != 200:
                    raise "balloon statistics error: " + resp.text
                result = resp.json()
                if result["target_mib"] != size or result["actual_mib"] != size:
                    time.sleep(0.01)
                else:
                    print("Firecracker-balloon scale {} {}MB use {:.1f}ms".format("down" if size == 0 else "up", size_,
                                                                                  (time.time() - start) * 1000))
                    break


def test_faaascale(sizes: list, socket_location: str):
    for size in sizes:
        url = f"http://192.168.0.3:5000/?size={size}"
        results = requests.get(url).json()
        print("Firecracker-faascale scale {} {}MB use {:.1f}ms".format("up", size, results['scale_up_uses']))
        print("Firecracker-faascale scale {} {}MB use {:.1f}ms".format("down", size, results['scale_down_uses']))


def stop_vmm():
    subprocess.run("sudo killall firecracker",
                   stderr=open("/dev/null", "w"), stdout=open("/dev/null", "w"), shell=True)
    subprocess.run("sudo killall qemu-system-x86_64",
                   stderr=open("/dev/null", "w"), stdout=open("/dev/null", "w"), shell=True)
    time.sleep(1)


def run_firecracker(params, sizes: list, type_: str):
    executer = params.executables.firecracker
    if type_ == "balloon":
        kernel = params.kernels.firecracker_balloon
    else:
        kernel = params.kernels.firecracker_faascale
    config = {
        "boot-source": {
            "kernel_image_path": kernel,
            # add console=ttyS0 will degrade the performance of faascale, because we print a lot of logs
            "boot_args": "reboot=k panic=1 pci=off random.trust_cpu=on i8042.nokbd i8042.noaux"
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": params.images.debian,
                "is_root_device": True,
                "is_read_only": True
            }
        ],
        "machine-config": {
            "vcpu_count": 2,
            "mem_size_mib": 8192,
            "track_dirty_pages": False
        },
        "network-interfaces": [
            {
                "iface_id": "eth0",
                "host_dev_name": "vmtap0",
                "guest_mac": "AA:FC:00:00:00:01"
            }
        ],
    }

    if type_ == "faascale":
        config["faascale-mem"] = {
            "pre_alloc_mem": False,
            "pre_tdp_fault": False,
            "stats_polling_interval_s": 0
        }
    else:
        config["balloon"] = {
            "amount_mib": 0,
            "deflate_on_oom": False,
            "stats_polling_interval_s": 1
        }

    with open("firecracker-configs/{}.json".format(type_), 'w') as f:
        json.dump(config, f)

    stop_vmm()
    subprocess.run("sudo rm -rf firecracker.sock", cwd=os.path.join(params.home_dir), shell=True)
    firecracker_pipe = subprocess.Popen(
        ["sudo", "/bin/ip", "netns", "exec", "fc1", executer, "--api-sock", "firecracker.sock",
         "--log-path", 'logs/firecracker-{}'.format(type_), "--config-file",
         "firecracker-configs/{}.json".format(type_)],
        stdout=open('logs/firecracker-{}'.format(type_), 'a+'),
        stderr=open('logs/firecracker-{}'.format(type_), 'a+'),
        cwd=os.path.join(params.home_dir))

    time.sleep(5)
    subprocess.run("sudo chmod 777 firecracker.sock", cwd=os.path.join(params.home_dir), shell=True)
    time.sleep(1)

    if type_ == "faascale":
        test_faaascale(sizes, os.path.join(params.home_dir, "firecracker.sock"))
    else:
        test_balloon(sizes, os.path.join(params.home_dir, "firecracker.sock"))

    subprocess.run("sudo rm -rf firecracker.sock", cwd=os.path.join(params.home_dir), shell=True)
    stop_vmm()
    firecracker_pipe.wait()


def run_qemu(params, sizes: list, type_: str):
    executer = params.executables.qemu
    kernel = params.kernels.qemu
    rootfs = params.images.debian

    qemu_cmd_args = ["sudo", executer, "-nographic", "-kernel", kernel,
                     "-append", "noinintr console=ttyS0 root=/dev/vda r loglevel=8 nokaslr",
                     "-drive", f"if=none,file={rootfs},id=hd0,format=raw", "-device", "virtio-blk-pci,drive=hd0",
                     "-qmp", "unix:/tmp/qmp.sock,server=on,wait=off",
                     "--enable-kvm", "-cpu", "host"]

    if type_ == "virtio_mem":
        qemu_cmd_args += ["-m", "2G,maxmem=10G", "-smp", "4",
                          "-object", "memory-backend-ram,id=vmem0,size=8G,prealloc=off",
                          "-device",
                          "virtio-mem-pci,id=vm0,memdev=vmem0,node=0,block-size=2M,prealloc=off",
                          "-qmp", "unix:/tmp/qmp.sock,server=on,wait=off"]
    elif type_ == "balloon":
        qemu_cmd_args += ["-m", "8G", "-smp", "4", "-device", "virtio-balloon"]

    stop_vmm()
    qemu_pipe = subprocess.Popen(qemu_cmd_args,
                                 stdout=open('logs/qemu-{}'.format(type_), 'a+'),
                                 stderr=open('logs/qemu-{}'.format(type_), 'a+'),
                                 cwd=params.home_dir)
    time.sleep(5)

    subprocess.Popen(["sudo", "-E", "./run.sh"],
                     stdout=open('logs/qemu-api-server-{}'.format(type_), 'a+'),
                     stderr=open('logs/qemu-api-server-{}'.format(type_), 'a+'),
                     cwd=os.path.join(params.home_dir, "qemu-api-server"))
    time.sleep(3)

    if type_ == "virtio_mem":
        max_size = 0
    else:
        max_size = 8192

    for size in sizes:
        url = f"http://localhost:8081/change_{type_}_to?value={abs(size - max_size)}"
        resp = requests.get(url, headers={'Content-Type': 'application/json'})

        print("Qemu-{} scale {} {}MB use {:.1f}ms".format(type_, "down" if type_ == "balloon" else "up", size,
                                                          resp.json()['use_time']))

        url = f"http://localhost:8081/change_{type_}_to?value={max_size}"
        resp = requests.get(url, headers={'Content-Type': 'application/json'})
        print("Qemu-{} scale {} {}MB use {:.1f}ms".format(type_, "up" if type_ == "balloon" else "down", size,
                                                          resp.json()['use_time']))

    stop_vmm()
    qemu_pipe.wait()


def run(params, setting: str, sizes: list, repeat: int):
    for r in range(repeat):
        print("\n=========%s scale: %d=========\n" % (setting, r))
        if setting.startswith("qemu"):
            run_qemu(params, sizes, setting[5:])
        else:
            run_firecracker(params, sizes, setting[12:])


def main(config_file):
    with open(config_file, 'r') as f:
        params = json.load(f, object_hook=lambda d: SimpleNamespace(**d))

    print(params.home_dir)
    # clear logs
    subprocess.run("sudo rm -rf logs/*", shell=True, cwd=params.home_dir)

    sizes = [512, 1024, 2048, 3072]

    for setting in params.settings:
        if setting == "qemu-balloon":
            continue
        if setting == "qemu-virtio_mem":
            continue
        if setting == "firecracker-balloon":
            continue
        if setting == "firecracker-faascale":
            pass
        run(params, setting, sizes, params.repeat)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: %s <test-scale.json>" % sys.argv[0])
        exit(1)
    if not os.path.exists(sys.argv[1]):
        print("File not found:", sys.argv[1])
        exit(1)
    main(sys.argv[1])

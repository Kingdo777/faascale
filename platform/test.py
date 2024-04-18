#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from multiprocessing.pool import Pool

import requests

sys.path.extend(["./platform/python-client"])
from swagger_client.api.default_api import DefaultApi
import swagger_client as daemon
from swagger_client.configuration import Configuration
from types import SimpleNamespace

bpf_map = {
    'brq': 'tracepoint:block:block_rq_issue /strncmp("fc_vcpu", comm, 7)==0 || comm =="main"/ {@blockrq[comm] = count(); @bsize[comm] = sum(args->bytes);}',
    'bsize': 'tracepoint:block:block_rq_issue /strncmp("fc_vcpu", comm, 7)==0 || comm =="main"/ {@blockrqsize[comm] = sum(args->bytes)}',
    '_bsize': 'tracepoint:block:block_rq_issue {@blockrqsize[comm] = sum(args->bytes)}',
    'pf': 'kprobe:handle_mm_fault /strncmp("fc_vcpu", comm, 7)==0 || comm =="main" || comm=="firecracker"/ {@pf[comm] = count()}',
    '_pf': 'kprobe:handle_mm_fault {@pf[comm] = count()}',
    'mpf': 'kretprobe:handle_mm_fault / (retval & 4) == 4 && (strncmp("fc_vcpu", comm, 7)==0 || comm =="main")/ {@majorpf[comm] = count()}',
    'pftime': 'kprobe:kvm_mmu_page_fault { @start[tid] = nsecs; } kretprobe:kvm_mmu_page_fault /@start[tid]/ {@n[comm] = count(); $delta = nsecs - @start[tid];  @dist[comm] = hist($delta); @avrg[comm] = avg($delta); delete(@start[tid]); }',
    'pfcount_time': 'kprobe:kvm_mmu_page_fault  {@start[tid] = nsecs;} kretprobe:kvm_mmu_page_fault /@start[tid]/ {@count = count(); $delta = nsecs - @start[tid];  @dist = hist($delta); @avrg = avg($delta); delete(@start[tid]); }',
    'vcpublock': 'kprobe:kvm_vcpu_block { @start[tid] = nsecs; } kprobe:kvm_vcpu_block /@start[tid]/ {@n[comm] = count(); $delta = nsecs - @start[tid];  @dist[comm] = hist($delta); @avrg[comm] = avg($delta); delete(@start[tid]); }',
    'cache': 'hardware:cache-misses:1000  /strncmp("fc_vcpu", comm, 7)==0/ {@misses[comm] = count()}',
    'mpf-tl': 'BEGIN { @start = nsecs; } kretprobe:handle_mm_fault / @start != 0 && (retval & 4) == 4 && (strncmp("fc_vcpu", comm, 7)==0 ) / { printf("%d\\n", (nsecs - @start) / 1000000); }'
}

clients = {}
conf = None

RESULT_DIR = "/tmp/faascale-evalution-results"
PAUSE = None
BPF = None


def add_network(client: DefaultApi, idx: int):
    ns = 'fc%d' % idx
    guest_mac = 'AA:FC:00:00:00:01'  # fixed MAC
    guest_addr = '172.16.0.2'  # fixed guest IP
    unique_addr = '192.168.0.%d' % (idx + 2)
    client.net_ifaces_namespace_put(namespace=ns, body={
        "host_dev_name": 'vmtap0',
        "iface_id": "eth0",
        "guest_mac": guest_mac,
        "guest_addr": guest_addr,
        "unique_addr": unique_addr
    })


def setup(params, setting, par, func):
    subprocess.Popen(["sudo", "killall", "main"], stdout=open('/tmp/out', 'a+'), stderr=open('/tmp/out', 'a+'))
    subprocess.Popen(["sudo", "killall", "firecracker"], stdout=open('/tmp/out', 'a+'),
                     stderr=open('/tmp/out', 'a+'))
    subprocess.Popen(["sudo", "killall", "firecracker-uffd"], stdout=open('/tmp/out', 'a+'),
                     stderr=open('/tmp/out', 'a+'))
    if params.test_dir != "":
        os.system("sudo rm -rf %s/*" % params.test_dir)
    time.sleep(1)

    # start daemon
    daemon_pipe = None
    daemon_pipe = subprocess.Popen(["sudo",
                                    './main',
                                    '--port=8080', '--host=0.0.0.0'], cwd=params.home_dir,
                                   stdout=open('%s/stdout' % RESULT_DIR, 'a+'), stderr=subprocess.STDOUT)
    time.sleep(5)

    # only one client for balloon and faascale
    if setting.name == "balloon" or setting.name == "faascale":
        par = 1

    # init clients, and add network
    for idx in range(1, 1 + par):
        clients[idx] = daemon.DefaultApi(daemon.ApiClient(conf))
        add_network(clients[idx], idx)

    # Create a new function use only one client to create snapshot
    client = clients[1]
    client.functions_post(body=daemon.Function(func_name=func.name, image=func.image, kernel=setting.kernel,
                                               vcpu=params.vcpu, mem_size=func.mem))

    return daemon_pipe


def clean_up(daemon_pipe):
    if daemon_pipe is not None:
        subprocess.Popen(["sudo", "killall", "main"], stdout=open('/tmp/out', 'a+'), stderr=open('/tmp/out', 'a+'))
        daemon_pipe.terminate()
        daemon_pipe.wait()
        time.sleep(1)


def start_bpf(run_id):
    if BPF:
        program = bpf_map[BPF]
        bpffile = open('%s/bpftrace' % (RESULT_DIR), 'a+')
        print('==== %s ====' % run_id, file=bpffile, flush=True)
        bpfpipe = subprocess.Popen(['sudo', 'bpftrace', '-e', program], cwd='/tmp/', stdout=bpffile,
                                   stderr=subprocess.STDOUT)
        time.sleep(3)
        return bpfpipe
    return None


def end_bpf(bpfpipe):
    assert ((bpfpipe is None) and (BPF is None)) or ((bpfpipe is not None) and (BPF is not None))
    if BPF:
        subprocess.Popen(["sudo", "killall", "bpftrace"])
        bpfpipe.terminate()
        bpfpipe.wait()


def prepare_snap(params, setting, func, func_param):
    client: DefaultApi
    client = clients[1]

    # create VM, the func_name use to define the image, kernel, and vcpu, these are submitted to the daemon when
    # creating the function. namespace is used to define the network.
    vm = client.vms_post(body={'func_name': func.name, 'namespace': 'fc%d' % 1})
    time.sleep(5)

    # define a invocation, specify the function name, vm_id, and the parameters
    invocation = daemon.Invocation(func_name=func.name, vm_id=vm.vm_id, params=func_param)

    # first invoke to prepare the snapshot
    ret = client.invocations_post(body=invocation)
    print('prepare invocation ret:', ret)

    # make the snapshot request
    body = daemon.Snapshot(vm_id=vm.vm_id, snapshot_type='Full', snapshot_path=params.test_dir + '/Full.snapshot',
                           mem_file_path=params.test_dir + '/Full.memfile', version='0.23.0')

    # create the snapshot
    snap = client.snapshots_post(body=body)

    # delete the VM
    client.vms_vm_id_delete(vm_id=vm.vm_id)
    time.sleep(2)

    # Important!!! for snapshot-cache, we need to load the snapshot to the page cache
    client.snapshots_ss_id_patch(ss_id=snap.ss_id, body=vars(setting.patch_state))
    time.sleep(1)
    return snap.ss_id


def invoke_snap(args):
    params, setting, func, func_param, idx, ss_id, par = args
    run_id = '%s_%s_%d' % (setting.name, func.id, par)

    # define a invocation, specify the ss_id, so the daemon will use the snapshot to create the VM
    invocation = daemon.Invocation(func_name=func.name, ss_id=ss_id, params=func_param, mincore=-1,
                                   namespace='fc%d' % idx, **vars(setting.invocation))

    # invoke the function
    bpf_pipe = start_bpf(run_id)
    ret = clients[idx].invocations_post(body=invocation)
    end_bpf(bpf_pipe)

    # delete the VM
    clients[idx].vms_vm_id_delete(vm_id=ret.vm_id)
    print('invoke', run_id, 'ret:', ret)
    time.sleep(2)


def run_snap(params, setting, par, func):
    # invoke the function, and create snapshot
    func_param = func.params
    snap_id = prepare_snap(params, setting, func, func_param)
    time.sleep(1)

    # re-invoke the function with snapshot
    if PAUSE:
        input("Press Enter to start...")
    with Pool(par) as p:
        vector = [(params, setting, func, func_param, idx, snap_id, par) for idx in range(1, 1 + par)]
        p.map(invoke_snap, vector)


def invoke_warm(args):
    client: DefaultApi
    params, setting, func, func_param, idx, vm_id = args
    client = clients[idx]
    run_id = '%s_%s' % (setting.name, func.id)
    time.sleep(1)
    invocation = daemon.Invocation(func_name=func.name, vm_id=vm_id, params=func_param)

    bpf_pipe = start_bpf(run_id)
    ret = client.invocations_post(body=invocation)
    end_bpf(bpf_pipe)

    print('2nd invocation ret:', ret)
    client.vms_vm_id_delete(vm_id=vm_id)
    time.sleep(2)


def run_warm(params, setting, par, func):
    func_params = func.params

    vms = {}
    for idx in range(1, 1 + par):
        vms[idx] = clients[idx].vms_post(body={'func_name': func.name, 'namespace': 'fc%d' % idx})
    time.sleep(5)

    for idx in range(1, 1 + par):
        invocation = daemon.Invocation(func_name=func.name, vm_id=vms[idx].vm_id, params=func_params)
        ret = clients[idx].invocations_post(body=invocation)
        print('1st invocation ret:', ret)
    time.sleep(1)

    if PAUSE:
        input("Press Enter to start...")
    with Pool(par) as p:
        vector = [(params, setting, func, func_params, idx, vms[idx].vm_id) for idx in range(1, 1 + par)]
        p.map(invoke_warm, vector)


def invoke_cold(args):
    client: DefaultApi
    params, setting, func, func_param, idx = args
    client = clients[idx]
    run_id = '%s_%s' % (setting.name, func.id)

    invocation = daemon.Invocation(func_name=func.name, params=func_param, namespace='fc%d' % idx)

    bpfpipe = start_bpf(run_id)
    start_time = time.time()
    ret = clients[idx].invocations_post(body=invocation)
    print('cold invoke time: {}ms'.format((time.time() - start_time) * 1000))
    end_bpf(bpfpipe)

    print('1st invocation ret:', ret)
    client.vms_vm_id_delete(vm_id=ret.vm_id)


def run_cold(params, setting, par, func):
    func_params = func.params

    with Pool(par) as p:
        vector = [(params, setting, func, func_params, idx) for idx in range(1, 1 + par)]
        p.map(invoke_cold, vector)


def invoke_vertical(args):
    client: DefaultApi
    client = clients[1]
    params, setting, func, func_param, vm_id, method = args
    run_id = '%s_%s' % (setting.name, func.id)
    time.sleep(1)

    invocation = daemon.Invocation(func_name=func.name, params=func_param, vm_id=vm_id)

    bpfpipe = start_bpf(run_id)
    start_time = time.time()
    ret = client.invocations_post(body=invocation)
    print('{} invoke time: {}ms'.format(method, (time.time() - start_time) * 1000))
    end_bpf(bpfpipe)

    print('1st invocation ret:', ret)


def run_vertical(params, setting, par, func, method):
    client: DefaultApi
    client = clients[1]
    func_params = func.params

    if method == "balloon":
        kernel = params.daemon.kernels.balloon
    else:
        kernel = params.daemon.kernels.faascale

    memory = func.mem * par + params.mem
    cpu = min(os.cpu_count(), params.vcpu + par)

    vm = client.vms_post(
        body={'func_name': func.name, 'namespace': 'fc%d' % 1,
              "kernel": kernel,
              "vcpu": cpu, "mem": memory,
              "enable_balloon": method == "balloon",
              "enable_faascale": method == "faascale"})
    time.sleep(5)

    with Pool(par) as p:
        vector = [(params, setting, func, func_params, vm.vm_id, method)]
        p.map(invoke_vertical, vector)

    client.vms_vm_id_delete(vm.vm_id)


def run(params, setting, func, par, repeat):
    for r in range(repeat):
        print("\n=========%s %s: %d=========\n" % (setting.name, func.id, r))
        # set up
        daemon_pipe = setup(params, setting, par, func)
        if setting.name == 'warm':
            run_warm(params, setting, par, func)
        elif setting.name == 'cold':
            run_cold(params, setting, par, func)
        elif setting.name == 'balloon':
            run_vertical(params, setting, par, func, "balloon")
        elif setting.name == 'faascale':
            run_vertical(params, setting, par, func, "faascale")
        else:
            run_snap(params, setting, par, func)
        # clean up
        clean_up(daemon_pipe)


def main(config_file):
    global conf
    os.system("rm -rf %s" % RESULT_DIR)
    os.makedirs(RESULT_DIR, mode=0o777, exist_ok=False)
    with open(config_file, 'r') as f:
        params = json.load(f, object_hook=lambda d: SimpleNamespace(**d))

    with open("/tmp/daemon.json", 'w') as f:
        json.dump(params.daemon, f, default=lambda o: o.__dict__, sort_keys=False, indent=4)
    conf = Configuration()
    conf.host = params.host

    print("repeat:", params.repeat)
    print("kernels:", params.daemon.kernels)
    print("vcpu:", params.vcpu)

    # BPF = "pfcount_time"
    # funcs = ["hello", "mmap", "read", "image"]
    # funcs = ['json', 'pyaes', 'compression', 'chameleon', 'matmul', 'pagerank', 'ffmpeg', 'recognition']
    funcs = ['hello']
    settings = ["cold", "vanilla", "vanilla-cache", "warm", "balloon", "faascale"]
    settings = ["cold"]
    for func in funcs:
        for setting in settings:
            run(params, vars(params.settings)[setting], vars(params.functions)[func], 1, 1)
            time.sleep(3)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: %s <test.json>" % sys.argv[0])
        exit(1)
    if not os.path.exists(sys.argv[1]):
        print("File not found:", sys.argv[1])
        exit(1)
    main(sys.argv[1])

# Platform

This platform is forked from [FaaSnap](https://github.com/ucsdsysnet/faasnap) and modified to support the Faascale
kernel. We use it to evaluate the performance of the Faascale and the snapshot mechanism.

# Setup

### Building the Firecracker.

1. Download Firecracker:
    - For FaaSnap: `clone https://github.com/ucsdsysnet/faasnap-firecracker`
    - For Faascale: `clone https://github.com/Kingdo777/faascale-firecracker`
2. Build Firecracker
    - `tools/devtool build -r release`
    - The built executable will be in `build/cargo_target/x86_64-unknown-linux-musl/release/firecracker`

### Compiling the Linux kernel for host and guest.

1. Download the guest kernel:
    - For FaaSnap: `clone https://github.com/ucsdsysnet/faasnap-kernel`
    - For Faascale guest: `clone https://github.com/Kingdo777/linux-5.10-faascale`
    - For Faascale host: `clone https://github.com/Kingdo777/linux-5.14.2-faascale-host`
2. Compile the kernels and install the Faascale host kernel to the host machine.

### Creating the guest rootfs image.

1. change to the prepare/rootfs directory: `cd prepare/rootfs`
2. Create base debian image: `./scripts/s1-create-debian-base-rootfs.sh`
3. Provision the base debian image: `./scripts/s2-provision-debian-rootfs.sh`
4. Copy functions to the rootfs: `./scripts/faascaletest`

### Building the platform.

1. Build API. `swagger generate server -f api/swagger.yaml`.
2. Build client. `swagger-codegen generate -l python -i api/swagger.yaml -o python-client`
3. Compile the daemon. `go get -u ./... && go build -o ./main github.com/ucsdsysnet/faasnap/cmd/faasnap-server`

### Configuring and preparing the environment.

1. Prepare the input data and Redis.
    - Start a local Redis instance on the default port 6379.
        - `docker run -d -p 6379:6379 redis`
    - Populate Redis with files in `resources` directory and its subdirectory. The keys should be the last parts of
      filenames (`basename`).
        - `pushd prepare/resources && .python3 populate_file_to_redis.py && popd`
2. Set the VM Network.
    - run the script `prepare/network/prep.sh` to create a network bridge.

# Evaluation workflow

1. Configuring the `test-funcytion.json` files.
    - In "daemon"
        - `base_path` is where firecracker VM logs, config and socket files location. Choose a directory in a local SSD.
        - `kernels` are the locations of balloon, faasnap and faascale kernels. The balloon's kernel is same as the
          faasnap kernel.
        - `images` is the rootfs location.
        - `executables` is the Firecracker binary for both faasnap ("vanilla") and faascale.
        - specify `redis_host` and `redis_passwd` accordingly.
    - `home_dir` is the current "platform" directory.
    - `test_dir` is where snapshot files location. Choose a directory in a local SSD.
    - Specify `host` and `trace_api`.
2. Run tests:
    - `sudo python3 test.py test-function.json`
    - After the tests finish, go to `http://<ip>:9411`, and use traceIDs to find trace results.

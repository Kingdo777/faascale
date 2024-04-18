# Setup

### Building the Firecracker and Qemu.

1. Download Firecracker:
    - `clone https://github.com/Kingdo777/faascale-firecracker`
2. Download Qemu:
    - For balloon and virtio-mem: `clone https://github.com/qemu/qemu.git`
3. Build Firecracker
    - `tools/devtool build -r release`
    - The built executable will be in `build/cargo_target/x86_64-unknown-linux-musl/release/firecracker`
4. Build Qemu
    - `mkdir build && cd build`
    - `../configure --target-list=x86_64-softmmu --python=/usr/bin/python3.10`
    - `make -j qemu-system-x86_64`
    - The built executable will be in `x86_64-softmmu/qemu-system-x86_64`

### Compiling the Linux kernels.

1. Download the guest kernel:
    - For Faascale guest: `clone https://github.com/Kingdo777/linux-5.10-faascale`
    - For Others guest: `clone https://github.com/Kingdo777/linux-5.10-faascale @5679377ec084b393302dc068eb3cadc5b6f24a64`
2. Compile the kernels.

### Creating the guest rootfs image.

1. change to the prepare/rootfs directory: `cd prepare/rootfs`
2. Create base debian image: `./scripts/s1-create-debian-base-rootfs.sh`
3. Provision the base debian image: `./scripts/s2-provision-debian-rootfs.sh`
4. Copy functions to the rootfs: `./scripts/s3-copy-faascaletest-to-debian-rootfs.sh`

### Configuring and preparing the environment.
1. Set the VM Network.
    - run the script `prepare/network/network.sh 1` to create a network bridge.

# Evaluation workflow

1. Configuring the `test-scale.json` files.
   - `kernels` are the locations kernels. The faascale use its dedicated kernel, others are using the default kernel.
   - `images` is the rootfs location.
   - `executables` is the Firecracker and Qemu binary.
2. Run tests:
    - `sudo python3 test.py test-scale.json`
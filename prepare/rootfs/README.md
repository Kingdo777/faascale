## Rootfs
To generate the guest rootfs, run the following command:
#### 1. Create base debian image
```bash
./scripts/s1-create-debian-base-rootfs.sh
```
#### 2. Provision the base debian image
```bash
./scripts/s2-provision-debian-rootfs.sh
```
#### 3. Copy functions to the rootfs
```bash
./scripts/s3-copy-functions-to-debian-rootfs.sh
```
or
```bash
./scripts/s3-copy-faascaletest-to-debian-rootfs.sh
```

#### 4. Do something you like
```bash
# This use to fix the bug of torch package
./scripts/s4-do-something.sh
```

## Benchmark functions

The benchmark functions are in `functions` directory.

The following functions are from [FunctionBench](https://github.com/kmu-bigdata/serverless-faas-workbench).
- chameleon
- image_processing
- json
- matmul
- pyaes

The following functions are from [SeBS](https://github.com/spcl/serverless-benchmarks).
- compression
- pagerank
- recognition

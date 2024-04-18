## Artifact Identification

This repository contains three artifacts related to the paper "Faascale: Scaling MicroVM Vertically for Serverless
Computing with Memory Elasticity". These artifacts are as follows:

- **Artifact A1:** A series of Python scripts for preprocessing Serverless workload datasets from Microsoft Azure and
  analyzing the number of cold starts and the quantity of MicroVMs needed to manage these workloads under various
  scaling strategies.
- **Artifact A2:** A comparison of existing memory scaling mechanisms, including Qemu's balloon and virtio-mem,
  Firecracker's balloon, and our proposed Faascale memory scaling strategy.
- **Artifact A3:** A serverless platform to evaluate the gains supplied by Faascale for serverless. The platform
  incorporates the traditional memory scaling strategy—memory ballooning—and the most advanced MicroVM snapshot
  technology.

### Artifact A1

**Source Directory:** *./feasibility*

**Installation Requirements:**

- **Hardware:** No special hardware requirements.
- **Software:** Supports any system running Python, including Linux, Windows, and macOS. The required Python version is
  3.10 or higher. The required Python packages are pandas, numpy, csv, and matplotlib.
- **Datasets/Inputs:** The dataset is the Serverless workload data set from Microsoft Azure, which can be
  downloaded [here](https://azurecloudpublicdataset2.blob.core.windows.net/azurepublicdatasetv2/azurefunctions_dataset2019/azurefunctions-dataset2019.tar.xz).
  More details can be found in
  the [README file](https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md).

**Execute the Artifact:**

Change the working directory to `feasibility`, and run the following commands in sequence:

- `python3 merge.py` (T1)
- `python3 coldstart.py` (T2)
- `python3 statistics.py` (T3)

The dependencies between the tasks are as follows: T1 → T2 and T1 → T3. Task T1 involves preprocessing the dataset to
generate a `feasibility/merged_data.csv` file, which serves as the input for subsequent processing by tasks T2 and T3.
Task T2 analyzes the number of cold starts under different scaling strategies, and task T3 analyzes the number of
MicroVMs required to handle the load under different scaling strategies. The results from T2 and T3 are output to
the `feasibility/cold-start-counts` and `feasibility/vm-counts` directories, respectively.

### Artifact A2

**Source Directory:** *./scale*

**Installation Requirements:**

- **Hardware:** Firecracker and Qemu require KVM support. Our experiments are conducted on a machine equipped with two
  28-core Xeon(R) Gold CPUs running at 2.00GHz, 256GB of DDR4 RAM at 2666 MHz, and a 2TB Intel SSD.
- **Software:** Ubuntu 22.04 TLS Linux with kernel version 5.14.2, Firecracker 1.5.0, Qemu 8.0.50, and Python 3.10.
- **Installation and Deployment:** Follow the instructions in the `scale/README.MD` file to install and deploy the
  artifact, which includes:
    - Building the Firecracker and Qemu.
    - Compiling the Linux kernels.
    - Creating the guest rootfs image.
    - Configuring and preparing the environment.

**Execute the Artifact:**
Change working directory to the `scale` directory and follow the instructions in the `README.MD` file to configure
the `test-scale.json` file. Then, execute `python3 test.py test-scale.json` with root privileges.

### Artifact A3

**Source Directory:** *./platform*

**Installation Requirements:**

- **Hardware:** Firecracker requires KVM support. Our experiments are conducted on a machine equipped with two 28-core
  Xeon(R) Gold CPUs running at 2.00GHz, 256GB of DDR4 RAM at 2666 MHz, and a 2TB Intel SSD.
- **Software:** Ubuntu 22.04 TLS Linux with kernel version 5.14.2, Firecracker 1.5.0, Docker 26.0.1, Golang 1.22.2,
  swagger 0.30.5, swagger-codegen 3.0.54 and Python 3.10.
- **Installation and Deployment:** Following the instructions in the `README.MD` file, to install and deploy the
  artifact, including:
    - Building the Firecracker.
    - Compiling the Linux kernel for host and guest.
    - Creating the guest rootfs image.
    - Building the platform.
    - Configuring and preparing the environment.

**Execute the Artifact:**
Change working directory to the `platform` and follow the instructions in the `README.MD` file to configure
the `test-function.json` file. Then, execute `python3 test.py test-function.json` with root privileges.

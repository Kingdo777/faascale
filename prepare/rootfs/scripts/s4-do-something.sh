#! /usr/bin/env bash
set -ex

IN=./debian-provisioned-rootfs.ext4
#IN=./debian-rootfs.ext4

sudo umount ./mountpoint || true
sudo rm -rf ./mountpoint
mkdir -p ./mountpoint

sudo mount $IN mountpoint
sudo cp scripts/s4-somethings.sh mountpoint/
sudo chroot mountpoint /bin/bash /s4-somethings.sh

sudo umount ./mountpoint


#! /usr/bin/env bash
set -ex

IN=debian-base-rootfs.ext4
OUT=debian-provisioned-rootfs.ext4
TMPOUT=.$OUT

sudo umount ./mountpoint || true
sudo rm -rf ./mountpoint
mkdir -p ./mountpoint
cp $IN $TMPOUT

sudo mount $TMPOUT mountpoint
sudo cp scripts/s2-provision-debian-rootfs.sh mountpoint/
sudo chroot mountpoint /bin/bash /s2-provision-debian-rootfs.sh

sudo umount mountpoint
mv $TMPOUT $OUT

#! /usr/bin/env bash

set -ex

IN=debian-provisioned-rootfs.ext4
OUT=debian-rootfs-for-scaletest.ext4
TMPOUT=.$OUT

CURRENT_DIR=$(dirname "$(realpath "$0")")
FUNCTIONS_DIR=$CURRENT_DIR/../faascale-test

sudo umount ./mountpoint || true
sudo rm -rf ./mountpoint
mkdir -p ./mountpoint
cp $IN $TMPOUT

sudo mount $TMPOUT mountpoint
sudo mkdir mountpoint/app
sudo cp -r "$FUNCTIONS_DIR"/* mountpoint/app/

sudo umount mountpoint
mv $TMPOUT $OUT

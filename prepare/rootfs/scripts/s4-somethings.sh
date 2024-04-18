#! /usr/bin/env bash
set -ex

#pip3 uninstall torch torchvision
#pip3 uninstall torch torchvision
#pip3 install torch==1.10.2 torchvision==0.11.3

#sed -i 's/ExecStart=python3 -m flask run --host=172.16.0.2/ExecStart=python3 \/app\/daemon.py/g' /etc/systemd/system/function-daemon.service
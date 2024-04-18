#!/usr/bin/env bash

set -eux

IFACE="$(route | grep '^default' | grep -o '[^ ]*$')"
CURR_DIR=$(dirname $0)

sudo setfacl -m u:${USER}:rw /dev/kvm

# network
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
sudo iptables -t nat -A POSTROUTING -o "${IFACE}" -j MASQUERADE
sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

#for i in {1..64}; do sudo ./network.sh $i ;done
sudo ./$CURR_DIR/network.sh 1

docker run -d -p 9411:9411 openzipkin/zipkin

#!/bin/sh

# install script for Ubuntu 20.04 x64

# ubuntu deps
apt-get update -y
apt-get upgrade -y

apt-get install -y git gcc python3-dev python3-venv python3-pip gpg

# mongo
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
apt-get update
apt-get install -y mongodb-org

# start server
systemctl enable mongod
systemctl start mongod

# app-server
pip3 install numpy
pip3 install bitstream bitstring pymongo httpserver requests

# chirp install
git clone https://github.com/RAKWireless/ChirpStack_on_Ubuntu.git
cd ChirpStack_on_Ubuntu
cp chirpstack-network-server_conf/chirpstack-network-server.us_902_928.toml ./chirpstack-network-server.toml
sh install.sh
cd ..


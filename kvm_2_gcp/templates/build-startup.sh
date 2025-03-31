#!/bin/bash

exec > /var/log/startup-script.log 2>&1
set -xe

if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  source /etc/os-release
else
  echo "Cannot detect OS."
  exit 1
fi

if [[ "$ID" =~ (debian|ubuntu) ]]; then
  apt update -y
  apt install -y python3.12 python3-apt
fi

if [[ "$ID" =~ (rhel|rocky|centos|fedora|ol) ]]; then
  dnf install -y python3.12 python3-dnf || yum install -y python3.12 python3-dnf
fi

echo "done" > /var/log/startup-done.marker
exit 0

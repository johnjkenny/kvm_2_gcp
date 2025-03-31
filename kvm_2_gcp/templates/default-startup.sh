#!/bin/bash

exec > /var/log/startup-script.log 2>&1
set -xe

echo "done" > /var/log/startup-done.marker
exit 0

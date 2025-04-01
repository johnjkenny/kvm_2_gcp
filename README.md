# KVM-2-GCP
This is a qa/dev/build/CI-CD tool for KVM and GCP

## Usage

Command Options:
```bash
k2g -h   
usage: k2g [-h] [-I ...] [-r ...] [-i ...] [--remoteDeploy REMOTEDEPLOY] [-d ...] [-b ...]

KVM-2-GCP Commands

options:
  -h, --help            show this help message and exit

  -I ..., --init ...    Initialize KVM-2-GCP environment

  -r ..., --remoteImages ...
                        Remote Images (k2g-remote-images)

  -i ..., --images ...  Images (k2g-images)

  --remoteDeploy REMOTEDEPLOY

  -d ..., --deploy ...  Deploy VM locally (KVM)

  -b ..., --build ...   Build custom image and push to GCP
```


### Initialization

The following will walk you through the initialization process. The initialization process will create a
virtual environment, install the required packages, and create the necessary directories and files. It will also
generate a private key for SSH access to the VM instance. The private key will be stored in `k2g_env/keys`. It will
stash the service account key in the `k2g_env/keys` directory as well. A directory structure will be created in `/k2g`
which will consists of the following directories:
- images: local images to use for KVM. Can manually import, download via remote image, or build custom images (clones)
- snapshots: snapshots of vm instances
- vms: vm instances that have been created


```bash
# Command options:
k2g -I -h
usage: k2g [-h] [-sa SERVICEACCOUNT] [-F]

KVM-2-GCP Initialization

options:
  -h, --help            show this help message and exit

  -sa SERVICEACCOUNT, --serviceAccount SERVICEACCOUNT
                        Service account path (full path to json file)

  -F, --force           Force action
```


1. Create virtual environment and install requirements:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2. Run the init command:
```bash
k2g -I -sa /home/myUser/sa.json
[2025-03-31 16:47:11,446][INFO][init,139]: Successfully initialized KVM-2-GCP Environment
```


# Display Available Remote Images:
This tool parses the remote repositories for image downloads and caches them locally to `/k2g/images/<family>_cache.json`.
In the below example, we are pulling the latest Rocky 9.x images located `https://download.rockylinux.org/pub/rocky/`.
As part of the caching process we store the total size of the image in bytes, sha256 checksum, family version,
architecture, and the url for the download process.

1. List Rocky Remote Images (drop `--refresh` to not update cache):
```bash
# same as: k2g -r -r -l -r
k2g --remote --rocky --list --refresh
# Example output:
[2025-03-30 17:09:24,148][INFO][remote_images,253]: Refreshing Rocky cloud image cache data
[2025-03-30 17:09:24,551][INFO][remote_images,223]: Pulling Rocky 9.5.x86_64 remote images
Rocky Remote Images:
  Rocky-9-Container-Minimal.latest.x86_64.tar.xz
  Rocky-9-Container-Base-9.5-20241118.0.x86_64.tar.xz
  Rocky-9-EC2-Base.latest.x86_64.qcow2
  Rocky-9-EC2-LVM-9.5-20241118.0.x86_64.qcow2
  Rocky-9-EC2.latest.x86_64.qcow2
  Rocky-9-OCP-Base.latest.x86_64.qcow2
  Rocky-9-Container-Base.latest.x86_64.tar.xz
  Rocky-9-OCP-Base-9.5-20241118.0.x86_64.qcow2
  Rocky-9-EC2-LVM.latest.x86_64.qcow2
  Rocky-9-EC2-Base-9.5-20241118.0.x86_64.qcow2
  Rocky-9-Container-Minimal-9.5-20241118.0.x86_64.tar.xz
  Rocky-9-GenericCloud.latest.x86_64.qcow2
  Rocky-9-Vagrant-Vbox.latest.x86_64.box
  Rocky-9-Vagrant-VMware-9.5-20241119.0.x86_64.box
  Rocky-9-GenericCloud-LVM-9.5-20241118.0.x86_64.qcow2
  Rocky-9-GenericCloud-Base.latest.x86_64.qcow2
  Rocky-9-Vagrant-Vbox-9.5-20241118.0.x86_64.box
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
  Rocky-9-GenericCloud-LVM.latest.x86_64.qcow2
  Rocky-9-Vagrant-VMware-9.5-20241118.0.x86_64.box
  Rocky-9-Container-UBI.latest.x86_64.tar.xz
  Rocky-9-Container-UBI-9.5-20241118.0.x86_64.tar.xz
  Rocky-9-Vagrant-VMware.latest.x86_64.box
  Rocky-9-Azure-Base.latest.x86_64.vhd
  Rocky-9-Vagrant-Libvirt-9.5-20241118.0.x86_64.box
  Rocky-9-Azure-LVM-9.5-20241118.0.x86_64.vhd
  Rocky-9-Azure.latest.x86_64.vhd
  Rocky-9-Vagrant-Libvirt.latest.x86_64.box
  Rocky-9-Azure-LVM.latest.x86_64.vhd
  Rocky-9-Azure-Base-9.5-20241118.0.x86_64.vhd
```

2. Example cache snip from `/k2g/images/rocky_cache.json`:
```json
{
"Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2": {
    "name": "Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2",
    "size": 609812480,
    "checksum": "069493fdc807300a22176540e9171fcff2227a92b40a7985a0c1c9e21aeebf57",
    "url": "https://download.rockylinux.org/pub/rocky/9.5/images/x86_64/Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2",
    "version": "9.5",
    "arch": "x86_64"
},
```

# Download a Remote Image:
Since we are using KVM it makes sense to stick to `qcow2` images. In this example we are going to download the
latest Rocky generic image, `Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2`. Local images are stored in
`/k2g/images` and a download progress bar is shown on console to help keep track of the download. After the download is
complete the downloaded content is verified against the sha256 checksum stored in the cache data. If the checksums
match then you will get a success message.

If you attempt to download the same image again a series of validation checks are performed on the local image to ensure
if exists. It will verify if the checksum of the local image matches the checksum stored in the cache data. if Rocky
updates the remote image, but keeps the same name then the checksum will be different. This is especially useful for
when you use `Rocky-9-GenericCloud.latest.x86_64.qcow2` as the image name will always be the same, but point to the
latest and greatest image; the checksum will not be the same. So incase you have a bad download (interrupted, etc) or
rocky made changes on their end you will be prompted on what you would like to do in such situations unless you use the
`--force` option.

1. Download remote image:
```bash
# same as: k2g -r -r -d
k2g --remote --rocky --download Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
Downloading: 100.00% complete
[2025-03-30 17:21:16,286][INFO][remote_images,160]: Successfully downloaded Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
```

2. Simulate bad download (interrupted):
```bash
# run download and cancel it via ctrl+c
k2g --remote --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2
Downloading: 1.20% complete
^C[2025-03-30 17:54:09,332][INFO][remote_images,156]: Download interrupted by user

# re-download the failed image (checksums mismatch expected):
k2g --remote --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2
[2025-03-30 17:55:50,402][INFO][remote_images,129]: Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists, but checksum does not match
Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists. Overwrite? (y/n):

# re-download the failed image using --force (checksums mismatch expected):
k2g --remote --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2 --force     
[2025-03-30 17:59:21,297][INFO][remote_images,129]: Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists, but checksum does not match
Downloading: 100.00% complete
[2025-03-30 18:02:04,668][INFO][remote_images,163]: Successfully downloaded Rocky-9-GenericCloud.latest.x86_64.qcow2

# re-download the success image (checksums match expected):
k2g --remote --rocky --download Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
Image Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2 exists. Overwrite? (y/n): n
```

# List Local Images:

```bash
# k2g -i -l
k2g --images --list
Images:
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
  Rocky-9-GenericCloud.latest.x86_64.qcow2
```

# Delete Local Image:
```bash
# Force action, drop --force (-F) to prompt for confirmation:
k2g --images --delete Rocky-9-GenericCloud.latest.x86_64.qcow2 --force
[2025-03-30 18:12:42,620][INFO][kvm_images,35]: Deleted image Rocky-9-GenericCloud.latest.x86_64.qcow2
```


### Deploy VM Locally (KVM)
The deploy has basic functionality. It allows you deploy a KVM instance using a linux image stored in `/k2g/images`.
It allows you specify a host name, but if you do not specify a name one will be generated using vm-<unique_id>.
The other options are to specify the number of CPUs and memory to use. The default is 2 CPUs and 2048MB (2GB) of memory.

The deploy process will add the ansible user and provide its public ssh key to the instance. If you are running the tool
with a non-root user then your current user name will also be added to the instance and your ssh public key will be parsed
from `~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`. Please ensure you have ssh keys generated before deploying an
instance. If you are running the tool with root or no ssh keys generated then you can only access the system using the
ansible user and its private key `k2g_env/keys/ansible_id_rsa`. Your username and the ansible user will have 
passwordless sudo access.

There is a basic startup script that runs on first boot and all it does is set a done flag in
`/var/log/startup-done.marker`. The deploy process will run an ansible playbook and use the ansible user to wait and
check for the existence of the done flag. This is to ensure the deploy process has completely finished and the init
ISO can be ejected, deleted, and the cdrom device removed from the instance.

```bash
# Command Options:

k2g --deploy -h
usage: k2g [-h] [-n NAME] [-i IMAGE] [-c CPU] [-m MEMORY]

KVM-2-GCP KVM Deploy

options:
  -h, --help            show this help message and exit

  -n NAME, --name NAME  Name of the VM. Default: GENERATE (vm-<unique_id>)

  -i IMAGE, --image IMAGE
                        Image to deploy

  -c CPU, --cpu CPU     Number of CPUs to use. Default: 2

  -m MEMORY, --memory MEMORY
                        Memory to use in MB. Default: 2048 (2GB)
```

1. Deploy a VM:
```bash
# List available images:
k2g -i -l      
Images:
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2

# Deploy image:
k2g --deploy --image Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
# example output:
Waiting for VM vm-2de60914 to initialize. 20/120 seconds
VM vm-2de60914 is up. IP: 192.168.124.75
Waiting for 192.168.124.75:22 to be open
192.168.124.75:22 is open, running Ansible playbook

PLAY [Wait for startup-done.marker on target VM] *******************************

TASK [Wait for startup script marker file] *************************************
ok: [vm-2de60914]

TASK [Success marker found] ****************************************************
ok: [vm-2de60914] => {
    "msg": "Startup completed — marker file detected."
}

PLAY RECAP *********************************************************************
vm-2de60914                : ok=2    changed=0    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-01 14:36:44,982][INFO][kvm_controller,437]: Ejected /k2g/vms/vm-2de60914/cidata.iso from vm-2de60914
[2025-04-01 14:36:45,200][INFO][kvm_controller,166]: Removed sdb from vm-2de60914
Successfully deployed VM vm-2de60914 IP: 192.168.124.75 User Access: ansible, myUser
```

2. Access the system:
```bash
# if you have a username and ssh keys generated with default naming convention in your homedir:
ssh 192.168.124.75
[myUser@vm-2de60914 ~]$ 
[myUser@vm-2de60914 ~]$ sudo su
[root@vm-2de60914 myUser]#

# User the ansible user:
ssh -i kvm_2_gcp/k2g_env/keys/.ansible_rsa ansible@192.168.124.75
[ansible@vm-2de60914 ~]$ sudo su
[root@vm-2de60914 ansible]#
```


### Control Local VMs (KVM)
The KVM controller allows you to start, stop, reboot, reset, delete and list VMs. It also allows you to list network
info, add or remove network interfaces, list disks and add or remove data disks and increase disk sizes. The network
handling is basic and only uses one host interface, `virbr0`. Adding interfaces to VMs will add another interface
from this bridge only and auto assign IP from the `/24` subnet.


```bash
k2g --controller -h
usage: k2g [-h] [-v VM] [-D] [-l] [-R] [-RH] [-RS] [-s] [-S] [-n ...]

KVM-2-GCP KVM Controller

options:
  -h, --help            show this help message and exit

  -v VM, --vm VM        Virtual machine name

  -D, --delete          Delete virtual machine

  -l, --list            List virtual machines

  -R, --reboot          Reboot virtual machine

  -RH, --resetHard      Reset virtual machine forcefully

  -RS, --resetSoft      Reset virtual machine gently

  -s, --start           Start virtual machine

  -S, --stop            Stop virtual machine

  -n ..., --networks ...
                        Virtual machine network interface handling

  -d ..., --disks ...   Virtual machine disk handling
```

1. List VMs:
```bash
k2g -c -l
VMs:
{
  "running": [
    "vm-2de60914"
  ],
  "stopped": [
    "share-client1",
    "share-server1",
    "vpn-client1",
    "vpn-server1"
  ],
  "paused": []
}
```

2. Start a VM:
```bash
k2g -c -v vm-2de60914 -s
[2025-04-01 14:58:31,063][INFO][kvm_controller,268]: Starting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.122.75
```

3. Stop a VM:
```bash
k2g -c -v vm-2de60914 -S
[2025-04-01 14:58:06,757][INFO][kvm_controller,229]: Shutting down VM vm-2de60914
Waiting for VM vm-2de60914 to shutdown. 1/60 seconds
```

4. Reboot a VM:
```bash
k2g -c -v vm-2de60914 -R
[2025-04-01 14:59:41,208][INFO][kvm_controller,329]: Rebooting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.122.75
```

5. Reset a VM:
```bash
# Soft reset (graceful, power off and power on):
k2g -c -v vm-2de60914 --resetSoft
[2025-04-01 15:00:28,317][INFO][kvm_controller,291]: Soft resetting VM vm-2de60914
[2025-04-01 15:00:28,317][INFO][kvm_controller,229]: Shutting down VM vm-2de60914
Waiting for VM vm-2de60914 to shutdown. 1/60 seconds
[2025-04-01 15:00:29,464][INFO][kvm_controller,268]: Starting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.122.75


# Hard reset (not graceful):
k2g -c -v vm-2de60914 --resetHard 
[2025-04-01 15:01:32,301][INFO][kvm_controller,307]: Hard resetting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.122.75
```

6. Delete a VM:
```bash
k2g -c -v vm-2de60914 -D 
[2025-04-01 15:02:47,090][INFO][kvm_controller,208]: Deleting VM vm-2de60914
[2025-04-01 15:02:47,116][INFO][kvm_controller,229]: Shutting down VM vm-2de60914
Waiting for VM vm-2de60914 to shutdown. 1/60 seconds
[2025-04-01 15:02:48,265][INFO][kvm_controller,33]: Deleting VM directory /k2g/vms/vm-2de60914

k2g -c -l
VMs:
{
  "running": [],
  "stopped": [
    "share-client1",
    "share-server1",
    "vpn-client1",
    "vpn-server1"
  ],
  "paused": []
}
```

### VM Network Interface Handling
```bash
# Command options:
k2g -c -v vm-d9a7792d -n -h                  
usage: k2g [-h] [-l] [-a] [-r REMOVE]

KVM-2-GCP KVM Network

options:
  -h, --help            show this help message and exit

  -l, --list            List VM network interfaces

  -a, --add             Add network interface to VM

  -r REMOVE, --remove REMOVE
                        Remove network interface from VM (specify MAC address)

```

1. List network info:
Depending on the state of the VM you will get different output and that is due to how the information is gathered.
If the VM is running we use the `virsh guestinfo` command to get the network info including the assigned IP
address. If the VM is not running we use the `virsh dumpxml` command to get the network interface data
```bash
# powered off:
k2g -c -v vm-d9a7792d -n -l                  
{
  "1": {
    "mac": "52:54:00:ea:83:86",
    "source": "virbr0",
    "model": "virtio"
  }
}

# powered on:
k2g -c -v vm-d9a7792d -n -l
{
  "1": {
    "name": "eth0",
    "mac": "52:54:00:ea:83:86",
    "ip": "192.168.122.173",
    "subnet": "/24"
  }
}
```

2. Add a network interface:
If you are adding a network interface to a powered on VM then it will seem like it is taking a long time to add. This
is because we are waiting for the IP address to populate which takes about 15 seconds.

```bash
# Powered on (15 second delay):
k2g -c -v vm-d9a7792d -n -a
[2025-04-01 18:31:02,101][INFO][kvm_controller,620]: Successfully attached network interface to vm-d9a7792d
{
  "1": {
    "name": "eth0",
    "mac": "52:54:00:ea:83:86",
    "ip": "192.168.122.173",
    "subnet": "/24"
  },
  "2": {
    "name": "eth1",
    "mac": "52:54:00:c3:bd:6f",
    "ip": "192.168.122.119",
    "subnet": "/24"
  }
}

# Powered off (no delay):
k2g -c -v vm-d9a7792d -n -a
[2025-04-01 18:32:09,708][INFO][kvm_controller,620]: Successfully attached network interface to vm-d9a7792d
{
  "1": {
    "mac": "52:54:00:ea:83:86",
    "source": "virbr0",
    "model": "virtio"
  },
  "2": {
    "mac": "52:54:00:c3:bd:6f",
    "source": "virbr0",
    "model": "virtio"
  },
  "3": {
    "mac": "52:54:00:e9:66:5e",
    "source": "virbr0",
    "model": "virtio"
  }
}
```

3. Remove a network interface:
```bash
# Powered off:
k2g -c -v vm-d9a7792d -n -r 52:54:00:e9:66:5e
[2025-04-01 18:33:21,882][INFO][kvm_controller,633]: Successfully removed network interface from vm-d9a7792d
{
  "1": {
    "mac": "52:54:00:ea:83:86",
    "source": "virbr0",
    "model": "virtio"
  },
  "2": {
    "mac": "52:54:00:c3:bd:6f",
    "source": "virbr0",
    "model": "virtio"
  }
}

# Powered on (no delay):
k2g -c -v vm-d9a7792d -n -r 52:54:00:c3:bd:6f
[2025-04-01 18:34:02,072][INFO][kvm_controller,633]: Successfully removed network interface from vm-d9a7792d
{
  "1": {
    "name": "eth0",
    "mac": "52:54:00:ea:83:86",
    "ip": "192.168.122.173",
    "subnet": "/24"
  }
}
```

### VM Disk Handling


```bash
# Command options:
k2g -c -v vm-d9a7792d -d -h
usage: k2g [-h] [-l] [-a] [-R REMOVE] [-n NAME] [-m MOUNTPOINT] [-u UNMOUNT] [-r REMOUNT]
           [-f FILESYSTEM] [-F] [-s SIZE]

KVM-2-GCP KVM Disks

options:
  -h, --help            show this help message and exit

  -l, --list            List virtual machine disks

  -a, --add             Add disk to virtual machine

  -R REMOVE, --remove REMOVE
                        Remove disk from virtual machine (specify device target e.g. sdb)

  -n NAME, --name NAME  Name of the disk. Default: GENERATE (data-<unique_id>)

  -m MOUNTPOINT, --mountPoint MOUNTPOINT
                        Mount point of the disk. Default: /mnt/<disk_name>

  -u UNMOUNT, --unmount UNMOUNT
                        Unmount a disk device (specify device target e.g. sdb)

  -r REMOUNT, --remount REMOUNT
                        Remount a disk device (specify device target e.g. sdb)

  -f FILESYSTEM, --filesystem FILESYSTEM
                        Filesystem type. Default: ext4

  -F, --force           Force action

  -s SIZE, --size SIZE  Disk size. Default: 1GB
```

1. List disks:
```bash
k2g -c -v vm-d9a7792d -d -l    
{
  "sda": {
    "location": "/k2g/vms/vm-d9a7792d/boot.qcow2",
    "serial": "vm-d9a7792d-boot",
    "size_bytes": 10737418240,
    "size": "10 GiB"
  }
}
```

2. Add a disk:
The add disk command will create the disk image, assign the disk to the VM, then if the VM is powered on it will
run an ansible playbook that will format the disk to the specified filesystem type and then mount the disk to the
specified mount point. An `fstab` entry will also be created using the device's UUID. The default filesystem type
is `ext4` and the default mount point is `/mnt/<disk_name>`. The filesystem create uses the mkfs.<filesystem> command
so realistically your two options are `ext4` or `xfs`, but if you install other packages that create the required mkfs
command mappers then your options grow. The tool does not create disk partitions, but rather uses the entire disk
image as a single partition.

```bash
# add disk using default options on a powered on VM:
k2g -c -v vm-d9a7792d -d -a 
[2025-04-01 22:56:49,447][INFO][kvm_controller,152]: Successfully created data disk /k2g/vms/vm-d9a7792d/data-ec41d3c9.qcow2 for vm-d9a7792d
[2025-04-01 22:56:49,663][INFO][kvm_controller,179]: Successfully attached data disk /k2g/vms/vm-d9a7792d/data-ec41d3c9.qcow2 to vm-d9a7792d

PLAY [Format disk with filesystem] *********************************************

TASK [Ensure device exists and is not formatted] *******************************
ok: [vm-d9a7792d]

TASK [Format disk] *************************************************************
changed: [vm-d9a7792d]

PLAY [Mount disk] **************************************************************

TASK [Ensure mount point directory exists] *************************************
changed: [vm-d9a7792d]

TASK [Get UUID of the device] **************************************************
ok: [vm-d9a7792d]

TASK [Mount the disk using UUID and add to fstab] ******************************
changed: [vm-d9a7792d]

PLAY RECAP *********************************************************************
vm-d9a7792d                : ok=5    changed=3    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-01 22:56:51,385][INFO][kvm_controller,529]: Successfully formatted and mounted /k2g/vms/vm-d9a7792d/data-ec41d3c9.qcow2 on vm-d9a7792d

# Check system:
df -Th | grep mnt
/dev/sdb       ext4      974M   24K  907M   1% /mnt/data-ec41d3c9

grep mnt /etc/fstab 
UUID=657de19e-64e1-4ed4-b2cc-a3b7280a44b2 /mnt/data-ec41d3c9 auto defaults 0 0


# Create a disk using custom options:
k2g -c -v vm-d9a7792d -d -a -f xfs -s 2586MB -m /mnt/myXFS -n data-xfs1
[2025-04-01 23:00:30,032][INFO][kvm_controller,152]: Successfully created data disk /k2g/vms/vm-d9a7792d/data-xfs1.qcow2 for vm-d9a7792d
[2025-04-01 23:00:30,284][INFO][kvm_controller,179]: Successfully attached data disk /k2g/vms/vm-d9a7792d/data-xfs1.qcow2 to vm-d9a7792d

PLAY [Format disk with filesystem] *********************************************

TASK [Ensure device exists and is not formatted] *******************************
ok: [vm-d9a7792d]

TASK [Format disk] *************************************************************
changed: [vm-d9a7792d]

PLAY [Mount disk] **************************************************************

TASK [Ensure mount point directory exists] *************************************
changed: [vm-d9a7792d]

TASK [Get UUID of the device] **************************************************
ok: [vm-d9a7792d]

TASK [Mount the disk using UUID and add to fstab] ******************************
changed: [vm-d9a7792d]

PLAY RECAP *********************************************************************
vm-d9a7792d                : ok=5    changed=3    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-01 23:00:32,002][INFO][kvm_controller,529]: Successfully formatted and mounted /k2g/vms/vm-d9a7792d/data-xfs1.qcow2 on vm-d9a7792d

# Check system:
df -Th | grep XFS
/dev/sdc       xfs       2.5G   50M  2.5G   2% /mnt/myXFS

grep XFS /etc/fstab 
UUID=d7daf9cd-de27-487f-86b6-7198fedfe874 /mnt/myXFS auto defaults 0 0

# List disks:
k2g -c -v vm-d9a7792d -d -l                                            
{
  "sda": {
    "location": "/k2g/vms/vm-d9a7792d/boot.qcow2",
    "serial": "vm-d9a7792d-boot",
    "size_bytes": 10737418240,
    "size": "10 GiB"
  },
  "sdb": {
    "location": "/k2g/vms/vm-d9a7792d/data-ec41d3c9.qcow2",
    "serial": "vm-d9a7792d-data-ec41d3c9",
    "size_bytes": 1073741824,
    "size": "1 GiB"
  },
  "sdc": {
    "location": "/k2g/vms/vm-d9a7792d/data-xfs1.qcow2",
    "serial": "vm-d9a7792d-data-xfs1",
    "size_bytes": 2711617536,
    "size": "2.525 GiB"
  }
}
```

3. Remove a disk:
The remove disk command will unmount the disk on OS, remove the fstab entry, remove the disk from the VM, then it will
prompt you if you would like to delete the disk image. You can use the `--force` or `-F` option to force the delete
operation without prompting.

```bash
k2g -c -v vm-d9a7792d -d -R sdc

PLAY [Unmount disk] ************************************************************

TASK [Get list of mounted devices] *********************************************
ok: [vm-d9a7792d]

TASK [Find mount point for device] *********************************************
ok: [vm-d9a7792d] => (item=/dev/sdc on /mnt/myXFS type xfs (rw,relatime,seclabel,attr2,inode64,logbufs=8,logbsize=32k,noquota))

TASK [Unmount the device] ******************************************************
changed: [vm-d9a7792d]

TASK [Remove fstab entry] ******************************************************
changed: [vm-d9a7792d]

PLAY RECAP *********************************************************************
vm-d9a7792d                : ok=4    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
[2025-04-01 23:06:27,075][INFO][kvm_controller,732]: Successfully unmounted sdc on vm-d9a7792d
[2025-04-01 23:06:27,252][INFO][kvm_controller,782]: Successfully removed disk sdc from vm-d9a7792d
Delete disk /k2g/vms/vm-d9a7792d/data-xfs1.qcow2 from vm-d9a7792d? [y/n]: y
[2025-04-01 23:06:32,932][INFO][kvm_controller,790]: Deleted disk /k2g/vms/vm-d9a7792d/data-xfs1.qcow2
```

4. Umount/Remount a disk:
You can unmount a disk using the `-u` option and you can remount a disk using the `-r` option. When remounting, you can
select a new mount point using the `-m` option.

```bash
# unmount:
k2g -c -v vm-d9a7792d -d -u sdb

PLAY [Unmount disk] ************************************************************

TASK [Get list of mounted devices] *********************************************
ok: [vm-d9a7792d]

TASK [Find mount point for device] *********************************************
ok: [vm-d9a7792d] => (item=/dev/sdb on /mnt/data-ec41d3c9 type ext4 (rw,relatime,seclabel))

TASK [Unmount the device] ******************************************************
changed: [vm-d9a7792d]

TASK [Remove fstab entry] ******************************************************
changed: [vm-d9a7792d]

PLAY RECAP *********************************************************************
vm-d9a7792d                : ok=4    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
[2025-04-01 23:11:25,240][INFO][kvm_controller,732]: Successfully unmounted sdb on vm-d9a7792d

# remount:
k2g -c -v vm-d9a7792d -d -r sdb -m /mnt/newMount

PLAY [Mount disk] **************************************************************

TASK [Ensure mount point directory exists] *************************************
changed: [vm-d9a7792d]

TASK [Get UUID of the device] **************************************************
ok: [vm-d9a7792d]

TASK [Mount the disk using UUID and add to fstab] ******************************
changed: [vm-d9a7792d]

PLAY RECAP *********************************************************************
vm-d9a7792d                : ok=3    changed=2    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-01 23:11:54,182][INFO][kvm_controller,756]: Successfully mounted sdb on vm-d9a7792d

# Check system:
df -Th | grep new
/dev/sdb       ext4      974M   24K  907M   1% /mnt/newMount
```


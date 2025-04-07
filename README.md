# KVM-2-GCP
This is a dev/qa/build/IaC/CI-CD tool for KVM and GCP

# Usage

Command Options:
```bash
k2g -h   
usage: k2g [-h] [-I ...] [-r ...] [-i ...] [--remoteDeploy REMOTEDEPLOY] [-d ...] [-b ...]

KVM-2-GCP Commands

options:
  -h, --help            show this help message and exit

  -I ..., --init ...    Initialize KVM-2-GCP environment

  -ri ..., --remoteImages ...
                        Remote Images (k2g-remote-images)

  -rd ..., --remoteDeploy ...
                        Deploy VM remotely (GCP)

  -i ..., --images ...  Images (k2g-images)

  -d ..., --deploy ...  Deploy VM locally (KVM)

  -c ..., --controller ...
                        Controller (k2g-controller)
```


# Initialization

The following will walk you through the initialization process. The initialization process will create a
virtual environment, install the required packages, and create the necessary directories and files. It will also
generate a private key for SSH access to the VM instance. The private key will be stored in `k2g_env/keys`. It will
stash the service account key in the `k2g_env/keys` directory as well. A directory structure will be created in `/k2g`
which will consists of the following directories:
- images: local images to use for KVM. Can manually import, download via remote image, or build custom images (clones)
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


# Remote Image Management:
This tool parses the remote repositories for image info and caches them locally to `/k2g/images/<family>_cache.json`.
The Rocky and Ubuntu options allow you to download the images locally and use them for local KVM deployments. Further
down the document it covers how to upload KVM images to GCP. The GCP option allows you to pull public and your private
images so you can choose to deploy under `--remoteDeploy` option. You cannot download GCP images directly from GCP, but
the images located in GCP can be downloaded from the family repositories (rocky ubuntu, etc).


```bash
# Command options:
k2g --remoteImages -h
usage: k2g [-h] [-r ...] [-u ...] [-g ...]

KVM-2-GCP Remote Images

options:
  -h, --help            show this help message and exit

  -r ..., --rocky ...   Rocky family remote images (k2g-remote-rocky-images)

  -u ..., --ubuntu ...  Ubuntu family remote images (k2g-remote-ubuntu-images)

  -g ..., --gcp ...     GCP remote images (k2g-remote-gcp-images)
```

## Rocky Remote Images
In the below example, we are pulling the latest Rocky 9.5 images located `https://download.rockylinux.org/pub/rocky/`.
As part of the caching process we store the total size of the image in bytes, sha256 checksum, family version,
architecture, and the url for the download process.

1. List Rocky Remote Images (drop `--refresh` to not update cache):
```bash
# same as: k2g -ri -r -l -r
k2g --remoteImages --rocky --list --refresh
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

3. Download a Remote Image:
Since we are using KVM it makes sense to stick to `qcow2` images. In this example we are going to download the
latest Rocky generic image, `Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2`. Local images are stored in
`/k2g/images` and a download progress bar is shown on console to help keep track of the download. After the download is
complete the downloaded content is verified against the sha256 checksum stored in the cache data. If the checksums
match then you will get a success message.

If you attempt to download the same image again a series of validation checks are performed on the local image to ensure
if exists. It will verify if the checksum of the local image matches the checksum stored in the cache data. If Rocky
updates the remote image, but keeps the same name then the checksum will be different. This is especially useful for
when you use `Rocky-9-GenericCloud.latest.x86_64.qcow2` as the image name will always be the same, but point to the
latest and greatest image; the checksum will not be the same. So incase you have a bad download (interrupted, etc) or
rocky made changes on their end you will be prompted on what you would like to do in such situations unless you use the
`--force` option.

- Download:
```bash
# same as: k2g -r -r -d
k2g --remoteImages --rocky --download Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
Downloading: 100.00% complete
[2025-03-30 17:21:16,286][INFO][remote_images,160]: Successfully downloaded Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
```

- Simulate bad download (interrupted):
```bash
# run download and cancel it via ctrl+c
k2g --remoteImages --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2
Downloading: 1.20% complete
^C[2025-03-30 17:54:09,332][INFO][remote_images,156]: Download interrupted by user

# re-download the failed image (checksums mismatch expected):
k2g --remoteImages --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2
[2025-03-30 17:55:50,402][INFO][remote_images,129]: Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists, but checksum does not match
Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists. Overwrite? (y/n):

# re-download the failed image using --force (checksums mismatch expected):
k2g --remoteImages --rocky --download Rocky-9-GenericCloud.latest.x86_64.qcow2 --force     
[2025-03-30 17:59:21,297][INFO][remote_images,129]: Image Rocky-9-GenericCloud.latest.x86_64.qcow2 exists, but checksum does not match
Downloading: 100.00% complete
[2025-03-30 18:02:04,668][INFO][remote_images,163]: Successfully downloaded Rocky-9-GenericCloud.latest.x86_64.qcow2

# re-download the success image (checksums match expected):
k2g --remoteImages --rocky --download Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
Image Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2 exists. Overwrite? (y/n): n
```

## GCP Remote Images
Lists the available images in GCP

```bash
# Command options:
k2g --remoteImages --gcp -h
usage: k2g [-h] [-l] [-p PROJECT] [-f FAMILY] [-s]

KVM-2-GCP GCP Remote Images

options:
  -h, --help            show this help message and exit

  -l, --list            List Images

  -n NAME, --name NAME  Name of the image. Default: GENERATE (image-<vm_name>)

  -p PROJECT, --project PROJECT
                        GCP project ID. Default: default

  -z ZONE, --zone ZONE  GCP zone. Default: us-central1-a

  -f FAMILY, --family FAMILY
                        Image family name. Default: k2g-images

  -F, --force           Force actions

  -s, --show            Show public image info for project and family

  -r, --refresh         Refresh cache data

  -c CLONE, --clone CLONE
                        Clone VM boot disk to image (specify VM name)
```

1. List your private images:
```bash
# add --project and --family to specify a different GCP project and image family
k2g --remoteImages --gcp --list
GCP k2g-images:
  image-vm-c3183891
```

2. Display basic public image options (project and family):
```bash
k2g --remoteImages --gcp --show
Project: debian-cloud, Family: debian-12
Project: ubuntu-os-cloud, Family: ubuntu-2404-lts-amd64
Project: rocky-linux-cloud, Family: rocky-linux-9-optimized-gcp
Project: cos-cloud, Family: cos-117-lts
```

3. Display public images:
```bash
k2g -ri -g -p ubuntu-os-cloud -f ubuntu-2404-lts-amd64 -l
GCP ubuntu-2404-lts-amd64:
  ubuntu-2404-noble-amd64-v20240423
...
  ubuntu-2404-noble-amd64-v20250214
  ubuntu-2404-noble-amd64-v20250228
  ubuntu-2404-noble-amd64-v20250313
```

4. Create an image from a GCP VM boot disk:
This next step creates an image from an already deployed VM in GCP. The VM needs to be stopped before creating the
image. If it is running you will be prompted to stop it unless you use the `--force` option.

```bash
k2g -ri -g -c vm-43ca6cf5 
Instance vm-43ca6cf5 is running. Stop it? (y/n): y
[2025-04-07 21:19:18,787][INFO][gcp_controller,172]: Stopping GCP instance vm-43ca6cf5
Waiting for operation operation-1744060759035-63236ca024de3-54157541-6298ef6b to complete...
Operation operation-1744060759035-63236ca024de3-54157541-6298ef6b completed successfully
Waiting for operation operation-1744061704222-632370258b8cf-0009bfc8-fcdf15bc to complete...
Operation operation-1744061704222-632370258b8cf-0009bfc8-fcdf15bc completed successfully

# list images to verify the image was created:
k2g -ri -g -l
GCP k2g-images:
  image-vm-43ca6cf5
  image-vm-c3183891
```

# KVM Image Management:
The image command allows you to list and delete local images. It also allows you to clone a VM boot disk to an image
and an option to upload an image to GCP to be used in the cloud.

```bash
# Command options:
k2g -i -h
usage: k2g [-h] [-l] [-c CLONE] [-n NAME] [-D DELETE] [-F]

KVM-2-GCP KVM Images

options:
  -h, --help            show this help message and exit

  -l, --list            List images

  -c CLONE, --clone CLONE
                        Clone VM boot disk to image (specify VM name)

  -n NAME, --name NAME  Name of the image. Default: GENERATE (image-<vm_name>)

  -D DELETE, --delete DELETE
                        Delete image

  -ug ..., --uploadGCP ...
                        Upload image to GCP

  -F, --force           Force action
```

1. List available images:
```bash
# k2g -i -l
k2g --images --list
Images:
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
  Rocky-9-GenericCloud.latest.x86_64.qcow2
```

2. Delete Local Image:
```bash
# Force action, drop --force (-F) to prompt for confirmation:
k2g --images --delete Rocky-9-GenericCloud.latest.x86_64.qcow2 --force
[2025-03-30 18:12:42,620][INFO][kvm_images,35]: Deleted image Rocky-9-GenericCloud.latest.x86_64.qcow2
```

3. Clone VM Boot Disk to Image:
```bash
k2g -i -c vm-c3183891
VM vm-c3183891 is running. Shutdown VM? [y/n] y
[2025-04-03 15:32:17,792][INFO][kvm_controller,260]: Shutting down VM vm-c3183891
Waiting for VM vm-c3183891 to shutdown. 1/60 seconds

k2g -i -l
Images:
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
  image-vm-c3183891.qcow2
```

4. Upload Image to GCP:
We will cover `--uploadGCP` option further down in the document under KVM Image Upload section


# Deploy VM Locally (KVM)
The deploy has basic functionality. It allows you deploy a KVM instance using a linux image stored in `/k2g/images`.
It allows you specify a host name, but one will be generated using `vm-<unique_id>` if omitted. The other options are
to specify the boot disk size in GB, number of CPUs and memory to use. The default is 10GB, 2 CPUs and 2048MB (2GB) of
memory.

The deploy process will add the ansible user and provide its public ssh key to the instance. If you are running the tool
with a non-root user then your current user name will also be added to the instance and your ssh public key will be parsed
from `~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`. Please ensure you have ssh keys generated before deploying an
instance. If you are running the tool with root or no ssh keys generated then you can only access the system using the
ansible user and its private key `k2g_env/keys/ansible_id_rsa`. Your username and the ansible user will have 
password-less sudo access.

There is a basic startup script that runs on first boot and all it does is set a done flag in
`/var/log/startup-done.marker`. The deploy process will run an ansible playbook and use the ansible user to wait and
check for the existence of the done flag. This is to ensure the deploy process has completely finished and the init
ISO can be ejected, deleted, and the cdrom device removed from the instance.

You will also have the ability to create custom images using the build command. More on that down on step 3.


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

  -s DISKSIZE, --diskSize DISKSIZE
                        Disk size in GB. Default: 10GB

  -c CPU, --cpu CPU     Number of CPUs to use. Default: 2

  -m MEMORY, --memory MEMORY
                        Memory to use in MB. Default: 2048 (2GB)

  -b ..., --build ...   Build KVM image
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
192.168.124.75:22 is open

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

3. Build Image:
The build command allows you to specify an ansible build playbook to run on the VM after it has been deployed. It will
then create a qcow2 image from the VM and store it in `/k2g/images`. On a successful build the VM will be deleted and
you can then deploy VMs from your custom image. The image will have the ansible user embedded with its public key. If
you do not intend for this to be in your custom image then please ensure you create an ansible task that will cleanup
the ansible user and public key as part of the build process. The build playbooks are stored in
`ansible/playbooks/builds`. The build tasks are located in `ansible/playbooks/tasks`.

The following example will deploy a build called `app1_build.yml` which installs docker on the VM and runs a
docker-compose file that deploys three containers, nginx, php, and mysql.

```bash
# build command options:
k2g -d -b -h                                                                        
usage: k2g [-h] [-l] [-p PLAYBOOK] [-P]

KVM-2-GCP KVM Builder

options:
  -h, --help            show this help message and exit

  -l, --list            List available ansible playbooks to run for the build process

  -p PLAYBOOK, --playbook PLAYBOOK
                        Ansible playbook to run for the build process


# List available builds:
k2g -d -b -l
Available builds:
  app1_build.yml


# run build:
k2g -d -i Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2 -b -p app1_build.yml
Waiting for VM build-2025-04-03--07-38-53 to initialize. 20/120 seconds
VM build-2025-04-03--07-38-53 is up. IP: 192.168.124.142
Waiting for 192.168.124.142:22 to be open
192.168.124.142:22 is open

PLAY [Build App1] **************************************************************

TASK [Gathering Facts] *********************************************************
ok: [build-2025-04-03--07-38-53]

TASK [Wait for startup script marker file] *************************************
ok: [build-2025-04-03--07-38-53]

TASK [Success marker found] ****************************************************
ok: [build-2025-04-03--07-38-53] => {
    "msg": "Startup completed — marker file detected."
}

TASK [Install dependencies (YUM/DNF)] ******************************************
changed: [build-2025-04-03--07-38-53]

TASK [Set up Docker repo on RedHat-family systems] *****************************
changed: [build-2025-04-03--07-38-53]

TASK [Install Docker CE] *******************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Enable and start Docker service] *****************************************
changed: [build-2025-04-03--07-38-53]

TASK [Create app directory structure] ******************************************
changed: [build-2025-04-03--07-38-53] => (item=web)
changed: [build-2025-04-03--07-38-53] => (item=php)
changed: [build-2025-04-03--07-38-53] => (item=mysql/db)

TASK [Copy Docker Compose file] ************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Copy web container files] ************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Copy php container files] ************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Copy db container files] *************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Copy web index file] *****************************************************
changed: [build-2025-04-03--07-38-53]

TASK [Write environment variables to file] *************************************
changed: [build-2025-04-03--07-38-53]

TASK [Set ownership of copied files] *******************************************
changed: [build-2025-04-03--07-38-53]

TASK [Deploy containers] *******************************************************
changed: [build-2025-04-03--07-38-53]

PLAY RECAP *********************************************************************
build-2025-04-03--07-38-53 : ok=16   changed=13   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0   
[2025-04-03 14:43:50,616][INFO][kvm_controller,515]: Ejected /k2g/vms/build-2025-04-03--07-38-53/cidata.iso from build-2025-04-03--07-38-53
[2025-04-03 14:43:51,155][INFO][kvm_controller,194]: Removed sdb from build-2025-04-03--07-38-53
Successfully deployed VM build-2025-04-03--07-38-53 IP: 192.168.124.142 User Access: ansible
[2025-04-03 14:43:51,183][INFO][kvm_controller,260]: Shutting down VM build-2025-04-03--07-38-53
Waiting for VM build-2025-04-03--07-38-53 to shutdown. 11/60 seconds
[2025-04-03 14:44:21,828][INFO][kvm_controller,238]: Deleting VM build-2025-04-03--07-38-53
[2025-04-03 14:44:27,942][INFO][kvm_controller,55]: Deleting VM directory /k2g/vms/build-2025-04-03--07-38-53
[2025-04-03 14:44:28,217][INFO][kvm_builder,55]: Successfully built image build-2025-04-03--07-38-53.qcow2

# List available images:
k2g -i -l                                                                           
Images:
  Rocky-9-GenericCloud-Base-9.5-20241118.0.x86_64.qcow2
  build-2025-04-03--07-38-53.qcow2


# deploy new image:
k2g -d -i build-2025-04-03--07-38-53.qcow2                                          
Waiting for VM vm-7954f510 to initialize. 25/120 seconds
VM vm-7954f510 is up. IP: 192.168.124.94
Waiting for 192.168.124.94:22 to be open
192.168.124.94:22 is open

PLAY [Wait for startup-done.marker on target VM] *******************************

TASK [Wait for startup script marker file] *************************************
ok: [vm-7954f510]

TASK [Success marker found] ****************************************************
ok: [vm-7954f510] => {
    "msg": "Startup completed — marker file detected."
}

PLAY RECAP *********************************************************************
vm-7954f510                : ok=2    changed=0    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-03 15:03:15,425][INFO][kvm_controller,515]: Ejected /k2g/vms/vm-7954f510/cidata.iso from vm-7954f510
[2025-04-03 15:03:15,965][INFO][kvm_controller,194]: Removed sdb from vm-7954f510
Successfully deployed VM vm-7954f510 IP: 192.168.124.94 User Access: ansible, myUser

# Access the system and verify the containers are running:
docker ps -a
CONTAINER ID   IMAGE      COMMAND                  CREATED          STATUS              PORTS                                 NAMES
4c6f01139303   app1_web   "/docker-entrypoint.…"   21 minutes ago   Up About a minute   0.0.0.0:80->80/tcp, [::]:80->80/tcp   app1-app1_web-1
b4e4fcefd59a   app1_php   "docker-php-entrypoi…"   21 minutes ago   Up About a minute   9000/tcp                              app1-app1_php-1
8155e2c1b864   app1_db    "/custom-entrypoint.…"   21 minutes ago   Up About a minute   3306/tcp, 33060/tcp                   app1-app1_db-1
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

  -F, --force           Force action

  -l, --list            List virtual machines

  -R, --reboot          Reboot virtual machine

  -RH, --resetHard      Reset virtual machine forcefully

  -RS, --resetSoft      Reset virtual machine gently

  -s, --start           Start virtual machine

  -S, --stop            Stop virtual machine

  -n ..., --networks ...
                        Virtual machine network interface handling

  -d ..., --disks ...   Virtual machine disk handling

  -r ..., --resources ...
                        Virtual machine resource handling
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
VM vm-2de60914 is up. IP: 192.168.124.75
```

3. Stop a VM:
```bash
# Will use hard-reset automatically after the 60 second grace period
k2g -c -v vm-2de60914 -S
[2025-04-01 14:58:06,757][INFO][kvm_controller,229]: Shutting down VM vm-2de60914
Waiting for VM vm-2de60914 to shutdown. 1/60 seconds
```

4. Reboot a VM:
```bash
k2g -c -v vm-2de60914 -R
[2025-04-01 14:59:41,208][INFO][kvm_controller,329]: Rebooting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.124.75
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
VM vm-2de60914 is up. IP: 192.168.124.75


# Hard reset (not graceful):
k2g -c -v vm-2de60914 --resetHard 
[2025-04-01 15:01:32,301][INFO][kvm_controller,307]: Hard resetting VM vm-2de60914
Waiting for VM vm-2de60914 to initialize. 10/120 seconds
VM vm-2de60914 is up. IP: 192.168.124.75
```

6. Delete a VM:
```bash
# Use --force (-F) to skip confirmation prompt:
k2g -c -v vm-2de60914 -D
Delete VM vm-2de60914 and all its data? [y/n]: y
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

## VM Network Interface Handling
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
    "ip": "192.168.124.173",
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
    "ip": "192.168.124.173",
    "subnet": "/24"
  },
  "2": {
    "name": "eth1",
    "mac": "52:54:00:c3:bd:6f",
    "ip": "192.168.124.119",
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
    "ip": "192.168.124.173",
    "subnet": "/24"
  }
}
```

## VM Disk Handling
This section will guide you in the process of adding, removing, and listing disks on a VM. It also allows you
to increase disk sizes when needed.

Please note, after the system reboots the disk device targets may change on OS side. `sdb` might become `/dev/sdc` etc.
This is OK, because as long as you use the device name from the output of `--disks --list` then the tool will find
the correct mapping on OS under `/dev/disk/by-id/` so any disk changes will be mapped correctly, but when checking
the OS the information might seem misleading.


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

  -i INCREASEDISK, --increaseDisk INCREASEDISK
                        Increase disk size. Specify the disk name (e.g. sda). Use --size to specify
                        increase size
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
is `ext4` and the default mount point is `/mnt/<disk_name>`. The filesystem format process uses the mkfs.<filesystem>
command so realistically your two options are `ext4` or `xfs`, but if you install other packages that create the
required mkfs command mappers then your options grow. The tool creates a primary partition on the disk (sdb1) then
creates the filesystem on the partition.

```bash
# add disk using default options on a powered on VM:
k2g -c -v vm-c3183891 -d -a
[2025-04-02 19:12:45,960][INFO][kvm_controller,159]: Successfully created data disk /k2g/vms/vm-c3183891/data-97e0a9ca.qcow2 for vm-c3183891
[2025-04-02 19:12:46,187][INFO][kvm_controller,186]: Successfully attached data disk /k2g/vms/vm-c3183891/data-97e0a9ca.qcow2 to vm-c3183891

PLAY [Format and mount data disk] **********************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Check if partition already exists] ***************************************
ok: [vm-c3183891]

TASK [Create partition on the disk] ********************************************
changed: [vm-c3183891]

TASK [Set device var to new partition device] **********************************
ok: [vm-c3183891]

TASK [Wait for partition to be recognized] *************************************
ok: [vm-c3183891]

TASK [Format the partition with ext4] ******************************************
changed: [vm-c3183891]

TASK [Ensure mount point directory exists] *************************************
changed: [vm-c3183891]

TASK [Get UUID of the device] **************************************************
ok: [vm-c3183891]

TASK [Mount the disk and add to fstab] *****************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=11   changed=4    unreachable=0    failed=0    skipped=3    rescued=0    ignored=0

# Check system:
df -Th | grep mnt
/dev/sdb1      ext4      988M   24K  921M   1% /mnt/data-9a33edf5

grep mnt /etc/fstab 
UUID=a89c81ed-32f7-4d52-9141-edabba926188 /mnt/data-9a33edf5 auto defaults,nofail,x-systemd.device-timeout=0 0 0


# Create a disk using custom options:
k2g -c -v vm-c3183891 -d -a -f xfs -s 2586MB -m /mnt/myXFS -n data-xfs1
[2025-04-02 19:13:06,658][INFO][kvm_controller,159]: Successfully created data disk /k2g/vms/vm-c3183891/data-xfs1.qcow2 for vm-c3183891
[2025-04-02 19:13:06,918][INFO][kvm_controller,186]: Successfully attached data disk /k2g/vms/vm-c3183891/data-xfs1.qcow2 to vm-c3183891

PLAY [Format and mount data disk] **********************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Check if partition already exists] ***************************************
ok: [vm-c3183891]

TASK [Create partition on the disk] ********************************************
changed: [vm-c3183891]

TASK [Set device var to new partition device] **********************************
ok: [vm-c3183891]

TASK [Wait for partition to be recognized] *************************************
ok: [vm-c3183891]

TASK [Format the partition with xfs] *******************************************
changed: [vm-c3183891]

TASK [Ensure mount point directory exists] *************************************
changed: [vm-c3183891]

TASK [Get UUID of the device] **************************************************
ok: [vm-c3183891]

TASK [Mount the disk and add to fstab] *****************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=11   changed=4    unreachable=0    failed=0    skipped=3    rescued=0    ignored=0   
[2025-04-02 19:13:09,149][INFO][kvm_controller,536]: Successfully formatted and mounted /k2g/vms/vm-c3183891/data-xfs1.qcow2 on vm-c3183891

# Check system:
df -Th | grep XFS
/dev/sdc1      xfs       2.5G   50M  2.5G   2% /mnt/myXFS

grep XFS /etc/fstab 
UUID=28204e75-d050-41a4-bc8c-177095ee77bc /mnt/myXFS auto defaults,nofail,x-systemd.device-timeout=0 0 0

# List disks:
k2g -c -v vm-c3183891 -d -l                                            
{
  "sda": {
    "location": "/k2g/vms/vm-c3183891/boot.qcow2",
    "serial": "vm-c3183891-boot",
    "size_bytes": 10737418240,
    "size": "10 GiB"
  },
  "sdb": {
    "location": "/k2g/vms/vm-c3183891/data-97e0a9ca.qcow2",
    "serial": "vm-c3183891-data-97e0a9ca",
    "size_bytes": 1073741824,
    "size": "1 GiB"
  },
  "sdc": {
    "location": "/k2g/vms/vm-c3183891/data-xfs1.qcow2",
    "serial": "vm-c3183891-data-xfs1",
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
k2g -c -v vm-05b3351b -d -R sdc                                        

PLAY [Unmount disk] ************************************************************

TASK [Get list of mounted devices] *********************************************
ok: [vm-05b3351b]

TASK [Find mount point for device] *********************************************
ok: [vm-05b3351b] => (item=/dev/sdc1 on /mnt/myXFS type xfs (rw,relatime,seclabel,attr2,inode64,logbufs=8,logbsize=32k,noquota,x-systemd.device-timeout=0))

TASK [Unmount the device] ******************************************************
changed: [vm-05b3351b]

TASK [Remove fstab entry] ******************************************************
changed: [vm-05b3351b]

PLAY RECAP *********************************************************************
vm-05b3351b                : ok=4    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
[2025-04-02 15:25:59,735][INFO][kvm_controller,731]: Successfully unmounted sdc on vm-05b3351b
[2025-04-02 15:25:59,911][INFO][kvm_controller,781]: Successfully removed disk sdc from vm-05b3351b
Delete disk /k2g/vms/vm-05b3351b/data-xfs1.qcow2 from vm-05b3351b? [y/n]: y
[2025-04-02 15:26:04,194][INFO][kvm_controller,789]: Deleted disk /k2g/vms/vm-05b3351b/data-xfs1.qcow2
```

4. Umount/Remount a disk:
You can unmount a disk using the `-u` option and you can remount a disk using the `-r` option. When remounting, you can
select a new mount point using the `-m` option.

```bash
# unmount:
k2g -c -v vm-c3183891 -d -u sdb

PLAY [Unmount disk] ************************************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Get list of mounted devices] *********************************************
ok: [vm-c3183891]

TASK [Find mount point for device] *********************************************
ok: [vm-c3183891] => (item=/dev/sdb1 on /mnt/data-97e0a9ca type ext4 (rw,relatime,seclabel,x-systemd.device-timeout=0))

TASK [Unmount the device] ******************************************************
changed: [vm-c3183891]

TASK [Remove fstab entry] ******************************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=7    changed=2    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
[2025-04-02 19:16:28,822][INFO][kvm_controller,740]: Successfully unmounted sdb on vm-c3183891


# remount:
k2g -c -v vm-c3183891 -d -r sdb -m /mnt/newMount

PLAY [Mount disk] **************************************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Ensure mount point directory exists] *************************************
changed: [vm-c3183891]

TASK [Get UUID of the device] **************************************************
ok: [vm-c3183891]

TASK [Mount the disk and add to fstab] *****************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=6    changed=2    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0   
[2025-04-02 19:16:49,808][INFO][kvm_controller,764]: Successfully mounted data-97e0a9ca-part1 on vm-c3183891

# Check system:
df -Th | grep new
/dev/sdb1      ext4      988M   24K  921M   1% /mnt/newMount
```

5. Increase disk size:
The increase disk size command requires the VM to be powered off. If you run the command while the VM is powered on
you will be prompted to power off the VM unless you use the `--force` option. The command will increase the disk size
of the specified disk by the specified size. After the resize the VM will be powered on and the disk will be resized
using `growpart`. Then it will be determined what filesystem is running and resize the filesystem using the appropriate
command, `resize2fs` for `ext4` and `xfs_growfs` for `xfs`.


```bash
# ext4 filesystem with prompt to power off:
k2g -c -v vm-c3183891 -d -i sdb -s 50M          
VM vm-c3183891 is running. Shutdown? [y/n]: y
[2025-04-02 19:20:06,197][INFO][kvm_controller,260]: Shutting down VM vm-c3183891
Waiting for VM vm-c3183891 to shutdown. 1/60 seconds
[2025-04-02 19:20:07,373][INFO][kvm_controller,832]: Successfully increased disk /k2g/vms/vm-c3183891/data-97e0a9ca.qcow2
[2025-04-02 19:20:07,373][INFO][kvm_controller,299]: Starting VM vm-c3183891
Waiting for VM vm-c3183891 to initialize. 10/120 seconds
VM vm-c3183891 is up. IP: 192.168.124.132

PLAY [Resize disk] *************************************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Extract disk and partition number] ***************************************
ok: [vm-c3183891]

TASK [Run growpart to resize partition] ****************************************
ok: [vm-c3183891]

TASK [Get filesystem type of partition] ****************************************
ok: [vm-c3183891]

TASK [Resize ext4 filesystem] **************************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=7    changed=1    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0   
[2025-04-02 19:20:20,736][INFO][kvm_controller,856]: Successfully resized disk sdb on vm-c3183891

k2g -c -v vm-c3183891 -d -l           
{
  "sda": {
    "location": "/k2g/vms/vm-c3183891/boot.qcow2",
    "serial": "vm-c3183891-boot",
    "size_bytes": 10737418240,
    "size": "10 GiB"
  },
  "sdb": {
    "location": "/k2g/vms/vm-c3183891/data-97e0a9ca.qcow2",
    "serial": "vm-c3183891-data-97e0a9ca",
    "size_bytes": 1126170624,
    "size": "1.049 GiB"
  },
  "sdc": {
    "location": "/k2g/vms/vm-c3183891/data-xfs1.qcow2",
    "serial": "vm-c3183891-data-xfs1",
    "size_bytes": 2711617536,
    "size": "2.525 GiB"
  }
}

# Check system:
df -Th | grep new
/dev/sdc1      ext4      1.1G   24K  968M   1% /mnt/newMount


# xfs filesystem with force option used:
k2g -c -v vm-c3183891 -d -i sdc -s 1.5G -F
[2025-04-02 19:23:13,795][INFO][kvm_controller,260]: Shutting down VM vm-c3183891
Waiting for VM vm-c3183891 to shutdown. 3/60 seconds
[2025-04-02 19:23:17,006][INFO][kvm_controller,832]: Successfully increased disk /k2g/vms/vm-c3183891/data-xfs1.qcow2
[2025-04-02 19:23:17,006][INFO][kvm_controller,299]: Starting VM vm-c3183891
Waiting for VM vm-c3183891 to initialize. 10/120 seconds
VM vm-c3183891 is up. IP: 192.168.124.132

PLAY [Resize disk] *************************************************************

TASK [Find device symlink in /dev/disk/by-id/] *********************************
ok: [vm-c3183891]

TASK [Resolve symlink to full /dev path] ***************************************
ok: [vm-c3183891]

TASK [Set resolved device path] ************************************************
ok: [vm-c3183891]

TASK [Extract disk and partition number] ***************************************
ok: [vm-c3183891]

TASK [Run growpart to resize partition] ****************************************
ok: [vm-c3183891]

TASK [Get filesystem type of partition] ****************************************
ok: [vm-c3183891]

TASK [Resize xfs filesystem] ***************************************************
changed: [vm-c3183891]

PLAY RECAP *********************************************************************
vm-c3183891                : ok=7    changed=1    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0   
[2025-04-02 19:23:30,364][INFO][kvm_controller,856]: Successfully resized disk sdc on vm-c3183891

k2g -c -v vm-c3183891 -d -l
{
  "sda": {
    "location": "/k2g/vms/vm-c3183891/boot.qcow2",
    "serial": "vm-c3183891-boot",
    "size_bytes": 10737418240,
    "size": "10 GiB"
  },
  "sdb": {
    "location": "/k2g/vms/vm-c3183891/data-97e0a9ca.qcow2",
    "serial": "vm-c3183891-data-97e0a9ca",
    "size_bytes": 1126170624,
    "size": "1.049 GiB"
  },
  "sdc": {
    "location": "/k2g/vms/vm-c3183891/data-xfs1.qcow2",
    "serial": "vm-c3183891-data-xfs1",
    "size_bytes": 4322230272,
    "size": "4.025 GiB"
  }
}
```

## VM Resource Handling
The resource command allows you to list and change VM CPU and memory assigned resources.

```bash
# command options:
k2g -c -r -h
usage: k2g [-h] [-l] [-c CPU] [-m MEMORY] [-F FORCE]

KVM-2-GCP KVM Resource Manager

options:
  -h, --help            show this help message and exit

  -l, --list            List virtual machine resources

  -c CPU, --cpu CPU     Set CPU count

  -m MEMORY, --memory MEMORY
                        Set memory size in MB

  -F FORCE, --force FORCE
                        Force action
```

1. List resources:
```bash
k2g -c -v vm-7e84bd43 -r -l
{
  "memory_bytes": 2147483648,
  "memory": "2 GiB",
  "cpu": 2
}
```

2. Change resources:
```bash
# Use the --force option to skip confirmation prompt:
k2g -c -v vm-7e84bd43 -r -c 4 -m 4096
VM vm-7e84bd43 is running. Shutdown? [y/n]: y
[2025-04-03 19:16:45,595][INFO][kvm_controller,260]: Shutting down VM vm-7e84bd43
Waiting for VM vm-7e84bd43 to shutdown. 3/60 seconds
[2025-04-03 19:16:48,827][INFO][kvm_controller,922]: Successfully set max CPU count for vm-7e84bd43 to 4
[2025-04-03 19:16:48,855][INFO][kvm_controller,926]: Successfully set current CPU count for vm-7e84bd43 to 4
[2025-04-03 19:16:48,883][INFO][kvm_controller,909]: Successfully set max memory for vm-7e84bd43 to 4194304 KiB
[2025-04-03 19:16:48,912][INFO][kvm_controller,913]: Successfully set current memory for vm-7e84bd43 to 4194304 KiB
[2025-04-03 19:16:48,912][INFO][kvm_controller,946]: Successfully set resources for vm-7e84bd43
[2025-04-03 19:16:48,912][INFO][kvm_controller,299]: Starting VM vm-7e84bd43
Waiting for VM vm-7e84bd43 to initialize. 10/120 seconds
VM vm-7e84bd43 is up. IP: 192.168.124.160

# relist resources:
k2g -c -v vm-7e84bd43 -r -l             
{
  "memory_bytes": 4294967296,
  "memory": "4 GiB",
  "cpu": 4
}
```


# KVM Image Upload
This tool allows you to upload KVM images to GCP. The tool is under `k2g --images --uploadGCP`. The tool uploads the
.qcow2 image to a GCP bucket, then it runs a cloud build job that imports the image to GCP. The .qcow2 image is uploaded
to the bucket in a subdirectory called `k2g-images`. The import uses a temp directory called `k2g-tmp` to store the
image build files. The tool will delete the uploaded .qcow2 image and the temp files after the build job runs as a
cleanup step.

```bash
# Command options:
k2g --images --uploadGCP -h
usage: k2g [-h] [-i IMAGE] [-n NAME] [-f FAMILY] [-b BUCKET] [-s SERVICEACCOUNT] [-p PROJECTID]

KVM-2-GCP Image Upload To GCP

options:
  -h, --help            show this help message and exit

  -i IMAGE, --image IMAGE
                        Image to upload

  -n NAME, --name NAME  Name of the image in GCP. Default: <image_name>

  -f FAMILY, --family FAMILY
                        Image family name to tag image in GCP. Default: k2g-images

  -b BUCKET, --bucket BUCKET
                        Bucket to use for image upload. Default: default

  -s SERVICEACCOUNT, --serviceAccount SERVICEACCOUNT
                        Service account to use. Default: default

  -p PROJECTID, --projectID PROJECTID
                        GCP project ID. Default: default
```

1. Upload KVM image to GCP:
```bash
# Using the default options:
k2g -i -ug -i image-vm-c3183891.qcow2 
[2025-04-04 19:30:41,519][INFO][gcp_image_upload,50]: Uploading image-vm-c3183891.qcow2 to GCP bucket
[2025-04-04 19:36:35,712][INFO][cloud_storage,191]: Successfully uploaded file /k2g/images/image-vm-c3183891.qcow2 to k2g-images/image-vm-c3183891.qcow2
[2025-04-04 19:36:36,896][INFO][gcp_image_upload,83]: Image import build started: 8e024e99-aab4-4cab-82bf-7885e3adc90d
Build 8e024e99-aab4-4cab-82bf-7885e3adc90d is running...
Build 8e024e99-aab4-4cab-82bf-7885e3adc90d is running...
...
[2025-04-04 19:47:12,850][INFO][gcp_image_upload,63]: Image import build completed successfully: 8e024e99-aab4-4cab-82bf-7885e3adc90d
[2025-04-04 19:47:13,363][INFO][cloud_storage,436]: Successfully deleted object k2g-images/image-vm-c3183891.qcow2
[2025-04-04 19:47:13,773][INFO][cloud_storage,441]: Successfully deleted object k2g-tmp/2025-04-04--12-30-41/

# Use the --remoteImages (-r) options to list the images in GCP:
k2g --remoteImages --gcp --list
GCP k2g-images:
  image-vm-c3183891
```


# Remote Deploy (GCP)
The command option `--remoteDeploy` allows you to deploy a VM in GCP. It has basic functionality which includes creating
a name for the VM, selecting the image for the deployment and the image project the image resides in, the zone the VM
will be deployed in and the machine type, the size of the boot disk, the boot disk type (HDD, BHD, SSD) and network
tags to assign to the VM. The default options will generate a name for the VM, use zone `us-central1-a`, machine type
`e2-highcpu-2` (2CPU, 2GB RAM), `pd-balanced` boot disk size of `10GB` and adds the network tag `ssh` to allow SSH
traffic in. It will also create a public IP address using the default VPC network and firewall rules.

Similar to the KVM deploy command, it will create an ansible user automatically and assign its public ssh key to the
VM instance meta data. If the command is run with a non-root user and the user has ssh keys generated then a user will
also be created on the VM and their public key will be added to the VM instance meta data. A startup script is added to
the VM meta data that simply marks a file `done` to signal the VM init process is complete. An ansible playbook will run
to verify this flag is set when a VM is deployed.

There is also an option to build a custom GCP image, `--build`. This option is similar to the KVM deploy build option
where it will deploy an image then configure the system using ansible. The process will run ansible build playbook,
power down the VM, then create an image from the VM boot disk. Then finally it will delete the VM.


```bash
# Command options:
k2g --remoteDeploy -h
usage: k2g [-h] [-n NAME] [-i IMAGE] [-ip IMAGEPROJECT] [-p PROJECTID] [-z ZONE] [-mt MACHINETYPE]
           [-s DISKSIZE] [-dt {pd-balanced,pd-ssd,pd-standard}] [-nt NETWORKTAGS [NETWORKTAGS ...]]
           [-b ...]

KVM-2-GCP Remote Deploy (GCP)

options:
  -h, --help            show this help message and exit

  -n NAME, --name NAME  Name of the VM. Default: GENERATE (vm-<unique_id>)

  -i IMAGE, --image IMAGE
                        Image to deploy

  -ip IMAGEPROJECT, --imageProject IMAGEPROJECT
                        GCP image project. Default: default

  -p PROJECTID, --projectID PROJECTID
                        GCP project ID. Default: default

  -z ZONE, --zone ZONE  GCP zone. Default: us-central1-a

  -mt MACHINETYPE, --machineType MACHINETYPE
                        GCP machine type. Default: e2-highcpu-2 (2 CPUs, 2GB RAM)

  -s DISKSIZE, --diskSize DISKSIZE
                        Disk size in GB. Default: 10GB

  -dt {pd-balanced,pd-ssd,pd-standard}, --diskType {pd-balanced,pd-ssd,pd-standard}
                        Disk type. Default: pd-balanced

  -nt NETWORKTAGS [NETWORKTAGS ...], --networkTags NETWORKTAGS [NETWORKTAGS ...]
                        Network tags for the VM. Default: ssh

  -b ..., --build ...   Build GCP image
```

1. Deploy VM using public image:
```bash
k2g -rd -i rocky-linux-9-optimized-gcp-v20250311 -ip rocky-linux-cloud -s 20
Waiting for operation operation-1744054500053-6323554f1d0ff-4fd0770d-91180bb4 to complete...
Operation operation-1744054500053-6323554f1d0ff-4fd0770d-91180bb4 completed successfully
Instance vm-c0ecbba0 created with external IP: 32.58.101.120
Waiting for 32.58.101.120:22 to be open
32.58.101.120:22 is not open. Retrying in 5 seconds
32.58.101.120:22 is open

PLAY [Wait for startup-done.marker on target VM] *******************************

TASK [Wait for startup script marker file] *************************************
ok: [vm-c0ecbba0]

TASK [Success marker found] ****************************************************
ok: [vm-c0ecbba0] => {
    "msg": "Startup completed — marker file detected."
}

PLAY RECAP *********************************************************************
vm-c0ecbba0                : ok=2    changed=0    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0   
Successfully deployed VM vm-c0ecbba0 IP: 32.58.101.120 User Access: ansible, myUser
```

2. Deploy VM using custom image:
```bash
k2g -rd -i image-vm-c3183891                           
Waiting for operation operation-1744046833953-632338c026b03-3bef794d-d91159de to complete...
Instance vm-ba7f2139 created with external IP: 33.224.114.110
Waiting for 33.224.114.110:22 to be open
33.224.114.110:22 is not open. Retrying in 5 seconds
33.224.114.110:22 is open
```

3. Build GCP image:
The following example will deploy a VM in GCP using latest Rocky 9.5 image and then uses ansible to install docker
and three containers on the VM; nginx, php and mysql. The VM will then be powered off and an image will be
created from the VM boot disk. The VM will then be deleted.


```bash
# list available builds:
k2g -rd -b -l
Available builds:
  app1_build.yml

k2g -rd -i rocky-linux-9-optimized-gcp-v20250311 -ip rocky-linux-cloud -s 20 -b -p app1_build.yml
Waiting for operation operation-1744064279129-632379bd2ac99-88e557e8-40f81680 to complete...
Operation operation-1744064279129-632379bd2ac99-88e557e8-40f81680 completed successfully
Instance build-2025-04-07--15-17-57 created with external IP: 32.172.51.98
Waiting for 32.172.51.98:22 to be open
32.172.51.98:22 is not open. Retrying in 5 seconds
32.172.51.98:22 is not open. Retrying in 5 seconds
32.172.51.98:22 is not open. Retrying in 5 seconds
32.172.51.98:22 is open

PLAY [Build App1] **************************************************************

TASK [Gathering Facts] *********************************************************
ok: [build-2025-04-07--15-17-57]

TASK [Wait for startup script marker file] *************************************
ok: [build-2025-04-07--15-17-57]

TASK [Success marker found] ****************************************************
ok: [build-2025-04-07--15-17-57] => {
    "msg": "Startup completed — marker file detected."
}

TASK [Install dependencies (YUM/DNF)] ******************************************
changed: [build-2025-04-07--15-17-57]

TASK [Set up Docker repo on RedHat-family systems] *****************************
[WARNING]: Module remote_tmp /root/.ansible/tmp did not exist and was created
with a mode of 0700, this may cause issues when running as another user. To
avoid this, create the remote_tmp dir with the correct permissions manually
changed: [build-2025-04-07--15-17-57]

TASK [Install Docker CE] *******************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Enable and start Docker service] *****************************************
changed: [build-2025-04-07--15-17-57]

TASK [Create app directory structure] ******************************************
changed: [build-2025-04-07--15-17-57] => (item=web)
changed: [build-2025-04-07--15-17-57] => (item=php)
changed: [build-2025-04-07--15-17-57] => (item=mysql/db)

TASK [Copy Docker Compose file] ************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Copy web container files] ************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Copy php container files] ************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Copy db container files] *************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Copy web index file] *****************************************************
changed: [build-2025-04-07--15-17-57]

TASK [Write environment variables to file] *************************************
changed: [build-2025-04-07--15-17-57]

TASK [Set ownership of copied files] *******************************************
changed: [build-2025-04-07--15-17-57]

TASK [Deploy containers] *******************************************************
changed: [build-2025-04-07--15-17-57]

PLAY RECAP *********************************************************************
build-2025-04-07--15-17-57 : ok=16   changed=13   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0   
Successfully deployed VM build-2025-04-07--15-17-57 IP: 32.172.51.98 User Access: ansible
[2025-04-07 22:23:02,391][INFO][gcp_controller,211]: Stopping GCP instance build-2025-04-07--15-17-57
Waiting for operation operation-1744064582629-63237ade9b84f-509676d5-4705a5b3 to complete...
Operation operation-1744064582629-63237ade9b84f-509676d5-4705a5b3 completed successfully
Waiting for operation operation-1744064614279-63237afccaaf8-f059f5d5-609b49f4 to complete...
Operation operation-1744064614279-63237afccaaf8-f059f5d5-609b49f4 completed successfully
[2025-04-07 22:25:38,758][INFO][gcp_controller,182]: Deleting GCP instance build-2025-04-07--15-17-57
Waiting for operation operation-1744064739069-63237b73ccec6-1c85c482-6ea17d0c to complete...
Operation operation-1744064739069-63237b73ccec6-1c85c482-6ea17d0c completed successfully
[2025-04-07 22:25:47,060][INFO][gcp_builder,50]: Successfully built image build-2025-04-07--15-17-57


# List images:
k2g -ri -g -l
GCP k2g-images:
  image-vm-c3183891
  build-2025-04-07--15-17-57
```


# Remote Controller (GCP)

```bash
# command options:
k2g -rc -h               
usage: k2g [-h] [-l] [-v VM] [-p PROJECTID] [-z ZONE] [-D] [-S] [-s] [-R]

KVM-2-GCP GCP Controller

options:
  -h, --help            show this help message and exit

  -l, --list            List instances

  -v VM, --vm VM        Virtual machine name

  -p PROJECTID, --projectID PROJECTID
                        GCP project ID. Default: default

  -z ZONE, --zone ZONE  GCP zone. Default: us-central1-a

  -D, --delete          Delete instance

  -S, --stop            Stop instance

  -s, --start           Start instance

  -R, --reboot          Reboot instance
```

1. List instances:
```bash
k2g -rc -l
{
  "running": [
    "vm-36048250"
  ],
  "stopped": []
}
```

2. Stop instance:
```bash
k2g -rc -S -v vm-36048250
[2025-04-07 20:25:31,021][INFO][gcp_controller,162]: Stopping GCP instance vm-36048250
Waiting for operation operation-1744057531137-63236099c7d94-ffba1436-130aab04 to complete...
Operation operation-1744057531137-63236099c7d94-ffba1436-130aab04 completed successfully

# check with list command:
k2g -rc -l               
{
  "running": [],
  "stopped": [
    "vm-36048250"
  ]
}
```

3. Start instance:
```bash
k2g -rc -s -v vm-36048250
[2025-04-07 20:26:52,125][INFO][gcp_controller,147]: Starting GCP instance vm-36048250
Waiting for operation operation-1744057612230-632360e71ddce-39ee9162-dab896f8 to complete...
Operation operation-1744057612230-632360e71ddce-39ee9162-dab896f8 completed successfully

# check with list command:
k2g -rc -l               
{
  "running": [
    "vm-36048250"
  ],
  "stopped": []
}

```

4. Reboot instance:
```bash
k2g -rc -R -v vm-36048250
[2025-04-07 20:27:43,153][INFO][gcp_controller,178]: Restarting GCP instance vm-36048250
Waiting for operation operation-1744057663252-63236117c6833-9c8b19a2-05a091cb to complete...
Operation operation-1744057663252-63236117c6833-9c8b19a2-05a091cb completed successfully

# check with list command:
k2g -rc -l               
{
  "running": [
    "vm-36048250"
  ],
  "stopped": []
}
```


5. Delete VM:

```bash
k2g -rc -D -v vm-36048250
[2025-04-07 20:29:25,033][INFO][gcp_controller,133]: Deleting GCP instance vm-36048250
Waiting for operation operation-1744057765329-632361791fa26-a1b178f9-21f133e1 to complete...
Operation operation-1744057765329-632361791fa26-a1b178f9-21f133e1 completed successfully

# check with list command:
k2g -rc -l               
{
  "running": [],
  "stopped": []
}
```

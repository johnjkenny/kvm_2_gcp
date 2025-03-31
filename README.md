# KVM-Controller


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
```bash

```

from argparse import REMAINDER

from kvm_2_gcp.arg_parser import ArgParser
from kvm_2_gcp.remote_images import RockyImages, GCPImages, UbuntuImages
from kvm_2_gcp.kvm_images import KVMImages
from kvm_2_gcp.kvm_deploy import KVMDeploy
from kvm_2_gcp.kvm_controller import KVMController
from kvm_2_gcp.kvm_builder import KVMBuilder
from kvm_2_gcp.gcp_deploy import GCPDeploy
from kvm_2_gcp.gcp_builder import GCPBuilder
from kvm_2_gcp.gcp_controller import GCPController


def parse_parent_args(args: dict):
    if args.get('controller'):
        return controller(args['controller'])
    if args.get('remoteImages'):
        return remote_images(args['remoteImages'])
    if args.get('images'):
        return images(args['images'])
    if args.get('deploy'):
        return deploy(args['deploy'])
    if args.get('remoteDeploy'):
        return remote_deploy(args['remoteDeploy'])
    if args.get('remoteController'):
        return remote_controller(args['remoteController'])
    if args.get('init'):
        return init(args['init'])
    return True


def k2g_parent():
    args = ArgParser('KVM-2-GCP Commands', None, {
        'init': {
            'short': 'I',
            'help': 'Initialize KVM-2-GCP environment (k2g-init)',
            'nargs': REMAINDER
        },
        'remoteImages': {
            'short': 'ri',
            'help': 'Remote Images (k2g-remote-images)',
            'nargs': REMAINDER
        },
        'remoteDeploy': {
            'short': 'rd',
            'help': 'Deploy VM remotely in GCP (k2g-remote-deploy)',
            'nargs': REMAINDER
        },
        'remoteController': {
            'short': 'rc',
            'help': 'Remote Controller (k2g-remote-controller)',
            'nargs': REMAINDER
        },
        'images': {
            'short': 'i',
            'help': 'Images (k2g-images)',
            'nargs': REMAINDER
        },
        'deploy': {
            'short': 'd',
            'help': 'Deploy VM locally with KVM (k2g-deploy)',
            'nargs': REMAINDER
        },
        'controller': {
            'short': 'c',
            'help': 'Controller (k2g-controller)',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_parent_args(args):
        exit(1)
    exit(0)


def parse_init_args(args: dict):
    from kvm_2_gcp.init import Init
    if args.get('serviceAccount'):
        return Init(args['serviceAccount'], args['bucket'], args['force']).run()
    return True


def init(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Initialization', parent_args, {
        'serviceAccount': {
            'short': 'sa',
            'help': 'Service account path (full path to json file)',
            'required': False,
        },
        'bucket': {
            'short': 'b',
            'help': 'Default bucket name to use for image upload',
            'default': ''
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true',
        },
    }).set_arguments()
    if not parse_init_args(args):
        exit(1)
    exit(0)


def parse_remote_image_args(args: dict):
    if args.get('rocky'):
        return rocky_remote_images(args['rocky'])
    if args.get('gcp'):
        return gcp_remote_images(args['gcp'])
    if args.get('ubuntu'):
        return ubuntu_remote_images(args['ubuntu'])
    return True


def remote_images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Remote Images', parent_args, {
        'rocky': {
            'help': 'Rocky family remote images (k2g-remote-rocky-images)',
            'nargs': REMAINDER
        },
        'ubuntu': {
            'help': 'Ubuntu family remote images (k2g-remote-ubuntu-images)',
            'nargs': REMAINDER
        },
        'gcp': {
            'help': 'GCP remote images (k2g-remote-gcp-images)',
            'nargs': REMAINDER
        },
    }).set_arguments()
    if not parse_remote_image_args(args):
        exit(1)
    exit(0)


def parse_rocky_remote_image_args(args: dict):
    if args.get('list'):
        return RockyImages().display_cache(args['refresh'])
    if args.get('download'):
        return RockyImages().download_image(args['download'], args['force'])
    if args.get('refresh'):
        return RockyImages().refresh_cache()
    return True


def rocky_remote_images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Rocky Remote Images', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List Images',
            'action': 'store_true'
        },
        'download': {
            'short': 'd',
            'help': 'Download remote image',
        },
        'refresh': {
            'short': 'R',
            'help': 'Refresh cache data',
            'action': 'store_true'
        },
        'force': {
            'short': 'F',
            'help': 'Force actions',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_rocky_remote_image_args(args):
        exit(1)
    exit(0)


def parse_ubuntu_remote_image_args(args: dict):
    if args.get('list'):
        return UbuntuImages().display_cache(args['refresh'], 'amd64')
    if args.get('download'):
        return UbuntuImages().download_image(args['download'], args['force'])
    if args.get('refresh'):
        return UbuntuImages().refresh_cache()
    return True


def ubuntu_remote_images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Ubuntu Remote Images', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List Images',
            'action': 'store_true'
        },
        'download': {
            'short': 'd',
            'help': 'Download remote image',
        },
        'refresh': {
            'short': 'R',
            'help': 'Refresh cache data',
            'action': 'store_true'
        },
        'arch': {
            'short': 'a',
            'help': 'Architecture to use. Default: amd64 (x86_64)',
            'default': 'amd64'
        },
        'force': {
            'short': 'F',
            'help': 'Force actions',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_ubuntu_remote_image_args(args):
        exit(1)
    exit(0)


def parse_gcp_remote_image_args(args: dict):
    if args.get('list'):
        return GCPImages(args['project']).display_images(args['family'], args['refresh'])
    if args.get('show'):
        return GCPImages(args['project']).display_public_image_info()
    if args.get('clone'):
        return GCPImages(args['project']).create_clone(args['zone'], args['clone'], args['name'], args['family'],
                                                       args['force'])
    return True


def gcp_remote_images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP GCP Remote Images', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List Images',
            'action': 'store_true'
        },
        'name': {
            'short': 'n',
            'help': 'Name of the image. Default: GENERATE (image-<vm_name>)',
            'default': 'GENERATE'
        },
        'project': {
            'short': 'p',
            'help': 'GCP project ID. Default: default',
            'default': 'default'
        },
        'zone': {
            'short': 'z',
            'help': 'GCP zone. Default: us-central1-a',
            'default': 'us-central1-a'
        },
        'family': {
            'short': 'f',
            'help': 'Image family name. Default: k2g-images',
            'default': 'k2g-images'
        },
        'force': {
            'short': 'F',
            'help': 'Force actions',
            'action': 'store_true'
        },
        'show': {
            'short': 's',
            'help': 'Show public image info for project and family',
            'action': 'store_true'
        },
        'refresh': {
            'short': 'R',
            'help': 'Refresh cache data',
            'action': 'store_true'
        },
        'clone': {
            'short': 'c',
            'help': 'Clone VM boot disk to image (specify VM name)',
        }
    }).set_arguments()
    if not parse_gcp_remote_image_args(args):
        exit(1)
    exit(0)


def parse_image_args(args: dict):
    if args.get('list'):
        return KVMImages().list_images()
    if args.get('delete'):
        return KVMImages().delete_image(args['delete'], args['force'])
    if args.get('clone'):
        return KVMImages().create_clone(args['clone'], args['name'], args['force'])
    if args.get('uploadGCP'):
        return upload_to_gcp(args['uploadGCP'])
    return True


def images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Images', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List images',
            'action': 'store_true'
        },
        'clone': {
            'short': 'c',
            'help': 'Clone VM boot disk to image (specify VM name)',
        },
        'name': {
            'short': 'n',
            'help': 'Name of the image. Default: GENERATE (image-<vm_name>)',
            'default': 'GENERATE'
        },
        'delete': {
            'short': 'D',
            'help': 'Delete image',
        },
        'uploadGCP': {
            'short': 'ug',
            'help': 'Upload image to GCP',
            'nargs': REMAINDER
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_image_args(args):
        exit(1)
    exit(0)


def parse_upload_to_gcp_args(args: dict):
    from kvm_2_gcp.gcp_image_upload import GCPImageUpload
    if args.get('image'):
        return GCPImageUpload(args['image'], args['name'], args['family'], args['bucket'], args['serviceAccount'],
                              args['projectID']).upload_image()
    return True


def upload_to_gcp(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Image Upload To GCP', parent_args, {
        'image': {
            'short': 'i',
            'help': 'Image to upload'
        },
        'name': {
            'short': 'n',
            'help': 'Name of the image in GCP. Default: <image_name>',
            'default': 'default'
        },
        'family': {
            'short': 'f',
            'help': 'Image family name to tag image in GCP. Default: k2g-images',
            'default': 'k2g-images'
        },
        'bucket': {
            'short': 'b',
            'help': 'Bucket to use for image upload. Default: default',
            'default': 'default'
        },
        'serviceAccount': {
            'short': 's',
            'help': 'Service account to use. Default: default',
            'default': 'default'
        },
        'projectID': {
            'short': 'p',
            'help': 'GCP project ID. Default: default',
            'default': 'default'
        },
    }).set_arguments()
    if not parse_upload_to_gcp_args(args):
        exit(1)
    exit(0)


def parse_deploy_args(args: dict):
    if args.get('image'):
        if args.get('build'):
            build_args = args.pop('build')
            return builder(args, build_args)
        return KVMDeploy(args['name'], args['image'], args['diskSize'], args['cpu'], args['memory']).deploy()
    if args.get('build'):
        build_args = args.pop('build')
        return builder(args, build_args)
    images = KVMImages()
    images.display_fail_msg('Image not specified. Please specify an image to deploy from the list below:')
    images.list_images()
    return True


def deploy(parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Deploy', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name of the VM. Default: GENERATE (vm-<unique_id>)',
            'default': 'GENERATE'
        },
        'image': {
            'short': 'i',
            'help': 'Image to deploy'
        },
        'diskSize': {
            'short': 's',
            'help': 'Disk size in GB. Default: 10GB',
            'type': int,
            'default': 10
        },
        'cpu': {
            'short': 'c',
            'help': 'Number of CPUs to use. Default: 2',
            'type': int,
            'default': 2
        },
        'memory': {
            'short': 'm',
            'help': 'Memory to use in MB. Default: 2048 (2GB)',
            'type': int,
            'default': 2048
        },
        'build': {
            'short': 'b',
            'help': 'Build KVM image',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_deploy_args(args):
        exit(1)
    exit(0)


def parse_controller_args(args: dict):
    if args.get('list'):
        return KVMController().list_vms()
    if args.get('networks'):
        return network(args.get('vm', ''), args['networks'])
    if args.get('hardware'):
        return hardware(args['vm'], args['hardware'])
    if args.get('disks'):
        return disks(args.get('vm', ''), args['disks'])
    if not args.get('vm'):
        return KVMController().display_fail_msg('VM name not specified. Please specify a VM name.')
    if args.get('start'):
        return KVMController().start_vm(args['vm'])
    if args.get('stop'):
        return KVMController().shutdown_vm(args['vm'])
    if args.get('reboot'):
        return KVMController().reboot_vm(args['vm'])
    if args.get('resetSoft'):
        return KVMController().soft_reset_vm(args['vm'])
    if args.get('resetHard'):
        return KVMController().hard_reset_vm(args['vm'])
    if args.get('delete'):
        return KVMController().delete_vm(args['vm'], args['force'])
    return True


def controller(parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Controller', parent_args, {
        'vm': {
            'short': 'v',
            'help': 'Virtual machine name',
        },
        'delete': {
            'short': 'D',
            'help': 'Delete virtual machine',
            'action': 'store_true'
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true'
        },
        'list': {
            'short': 'l',
            'action': 'store_true',
            'help': 'List virtual machines'
        },
        'reboot': {
            'short': 'R',
            'help': 'Reboot virtual machine',
            'action': 'store_true'
        },
        'resetHard': {
            'short': 'RH',
            'help': 'Reset virtual machine forcefully',
            'action': 'store_true'
        },
        'resetSoft': {
            'short': 'RS',
            'help': 'Reset virtual machine gently',
            'action': 'store_true'
        },
        'start': {
            'short': 's',
            'help': 'Start virtual machine',
            'action': 'store_true'
        },
        'stop': {
            'short': 'S',
            'help': 'Stop virtual machine',
            'action': 'store_true'
        },
        'networks': {
            'short': 'n',
            'help': 'Virtual machine network interface handling',
            'nargs': REMAINDER
        },
        'disks': {
            'short': 'd',
            'help': 'Virtual machine disk handling',
            'nargs': REMAINDER
        },
        'hardware': {
            'short': 'H',
            'help': 'Virtual machine hardware resource handling',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_controller_args(args):
        exit(1)
    exit(0)


def parse_network_args(vm_name: str, args: dict):
    if not vm_name:
        return KVMController().display_fail_msg('VM name not specified. Please specify a VM name.')
    if args.get('list'):
        return KVMController().display_vm_interfaces(vm_name)
    if args.get('add'):
        return KVMController().add_network_interface(vm_name)
    if args.get('remove'):
        KVMController().remove_network_interface(vm_name, args['remove'])
    return True


def network(vm_name: str, parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Network', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List virtual machine network interfaces',
            'action': 'store_true'
        },
        'add': {
            'short': 'a',
            'help': 'Add network interface to virtual machine',
            'action': 'store_true'
        },
        'remove': {
            'short': 'R',
            'help': 'Remove network interface from virtual machine (specify MAC address)',
        }
    }).set_arguments()
    if not parse_network_args(vm_name, args):
        exit(1)
    exit(0)


def parse_disk_args(vm_name: str, args: dict):
    if not vm_name:
        return KVMController().display_fail_msg('VM name not specified. Please specify a VM name.')
    if args.get('list'):
        return KVMController().display_vm_disks(vm_name)
    if args.get('add'):
        return KVMController().create_data_disk(vm_name, args['size'], args['name'], args['filesystem'],
                                                args['mountPoint'])
    if args.get('remove'):
        return KVMController().remove_data_disk(vm_name, args['remove'], args['force'])
    if args.get('unmount'):
        return KVMController().unmount_system_disk(vm_name, args['unmount'])
    if args.get('remount'):
        return KVMController().mount_system_disk(vm_name, args['remount'], args['mountPoint'])
    if args.get('increaseDisk'):
        return KVMController().increase_disk_size(vm_name, args['increaseDisk'], args['size'], args['force'])
    return True


def disks(vm_name: str, parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Disks', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List virtual machine disks',
            'action': 'store_true'
        },
        'add': {
            'short': 'a',
            'help': 'Add disk to virtual machine',
            'action': 'store_true'
        },
        'remove': {
            'short': 'R',
            'help': 'Remove disk from virtual machine (specify device target e.g. sdb)',
        },
        'name': {
            'short': 'n',
            'help': 'Name of the disk. Default: GENERATE (data-<unique_id>)',
            'default': 'GENERATE'
        },
        'mountPoint': {
            'short': 'm',
            'help': 'Mount point of the disk. Default: /mnt/<disk_name>',
            'default': 'default'
        },
        'unmount': {
            'short': 'u',
            'help': 'Unmount a disk device (specify device target e.g. sdb)',
        },
        'remount': {
            'short': 'rm',
            'help': 'Remount a disk device (specify device target e.g. sdb)',
        },
        'filesystem': {
            'short': 'f',
            'help': 'Filesystem type. Default: ext4',
            'default': 'ext4',
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true'
        },
        'size': {
            'short': 's',
            'help': 'Disk size. Default: 1GB',
            'default': '1GB',
        },
        'increaseDisk': {
            'short': 'i',
            'help': 'Increase disk size. Specify the disk name (e.g. sda). Use --size to specify increase size',
        },
    }).set_arguments()
    if not parse_disk_args(vm_name, args):
        exit(1)
    exit(0)


def parse_hardware_args(vm_name: str, args: dict):
    if not vm_name:
        return KVMController().display_fail_msg('VM name not specified. Please specify a VM name.')
    if args.get('list'):
        return KVMController().display_resources(vm_name)
    if args.get('cpu') or args.get('memory'):
        return KVMController().set_vm_resources(vm_name, args.get('cpu', 0), args.get('memory', 0), args['force'])
    return True


def hardware(vm_name: str, parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Hardware Manager', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List virtual machine resources',
            'action': 'store_true'
        },
        'cpu': {
            'short': 'c',
            'help': 'Set CPU count',
            'type': int,
        },
        'memory': {
            'short': 'm',
            'help': 'Set memory size in MB',
            'type': int,
        },
        'force': {
            'short': 'F',
            'help': 'Force action',
            'action': 'store_true'
        }
    }).set_arguments()
    if not parse_hardware_args(vm_name, args):
        exit(1)
    exit(0)


def parse_builder_args(dargs: dict, args: dict):
    if args.get('list'):
        return KVMBuilder().display_build_options()
    if args.get('playbook'):
        if not dargs.get('image'):
            return KVMBuilder().display_fail_msg('Image not specified for deploy')
        return KVMBuilder(dargs['name'], dargs['image'], dargs['diskSize'], dargs['cpu'], dargs['memory'],
                          args['playbook']).run_build()
    return True


def builder(deploy_args: dict, parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Builder', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List available ansible playbooks to run for the build process',
            'action': 'store_true'
        },
        'playbook': {
            'short': 'p',
            'help': 'Ansible playbook to run for the build process',
        },
    }).set_arguments()
    if not parse_builder_args(deploy_args, args):
        exit(1)
    exit(0)


def parse_remote_deploy_args(args: dict):
    if args.get('image'):
        if args.get('build'):
            build_args = args.pop('build')
            return gcp_builder(args, build_args)
        return GCPDeploy(args['name'], args['image'], args['imageProject'], args['diskSize'], args['diskType'],
                         args['projectID'], args['zone'], args['machineType'], args['networkTags']).deploy()
    if args.get('build'):
        build_args = args.pop('build')
        return gcp_builder(args, build_args)
    return True


def remote_deploy(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Remote Deploy (GCP)', parent_args, {
        'name': {
            'short': 'n',
            'help': 'Name of the VM. Default: GENERATE (vm-<unique_id>)',
            'default': 'GENERATE'
        },
        'image': {
            'short': 'i',
            'help': 'Image to deploy'
        },
        'imageProject': {
            'short': 'ip',
            'help': 'GCP image project. Default: default',
            'default': 'default'
        },
        'projectID': {
            'short': 'p',
            'help': 'GCP project ID. Default: default',
            'default': 'default'
        },
        'zone': {
            'short': 'z',
            'help': 'GCP zone. Default: us-central1-a',
            'default': 'us-central1-a'
        },
        'machineType': {
            'short': 'mt',
            'help': 'GCP machine type. Default: e2-highcpu-2 (2 CPUs, 2GB RAM)',
            'default': 'e2-highcpu-2'
        },
        'diskSize': {
            'short': 's',
            'help': 'Disk size in GB. Default: 10GB',
            'type': int,
            'default': 10
        },
        'diskType': {
            'short': 'dt',
            'help': 'Disk type. Default: pd-balanced',
            'choices': ['pd-balanced', 'pd-ssd', 'pd-standard'],
            'default': 'pd-balanced'
        },
        'networkTags': {
            'short': 'nt',
            'help': 'Network tags for the VM. Default: ssh',
            'nargs': '+',
            'default': ['ssh']
        },
        'build': {
            'short': 'b',
            'help': 'Build GCP image',
            'nargs': REMAINDER
        }
    }).set_arguments()
    if not parse_remote_deploy_args(args):
        exit(1)
    exit(0)


def parse_gcp_builder_args(dargs: dict, args: dict):
    if args.get('list'):
        return GCPBuilder().display_build_options()
    if args.get('playbook'):
        if not dargs.get('image'):
            return GCPBuilder().display_fail_msg('Image not specified for deploy')
        return GCPBuilder(dargs['name'], dargs['image'], dargs['imageProject'], dargs['diskSize'], dargs['diskType'],
                          dargs['projectID'], dargs['zone'], dargs['machineType'], dargs['networkTags'],
                          args['playbook'], args['family']).run_build()
    return True


def gcp_builder(deploy_args: dict, parent_args: list = None):
    args = ArgParser('KVM-2-GCP GCP Builder', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List available ansible playbooks to run for the build process',
            'action': 'store_true'
        },
        'family': {
            'short': 'f',
            'help': 'Image family name. Default: k2g-images',
            'default': 'k2g-images'
        },
        'playbook': {
            'short': 'p',
            'help': 'Ansible playbook to run for the build process',
        },
    }).set_arguments()
    if not parse_gcp_builder_args(deploy_args, args):
        exit(1)
    exit(0)


def parse_remote_controller_args(args: dict):
    if args.get('list'):
        GCPController().display_instances(args['projectID'], args['zone'])
    if args.get('start'):
        return GCPController().start_instance(args['projectID'], args['zone'], args['vm'])
    if args.get('stop'):
        return GCPController().stop_instance(args['projectID'], args['zone'], args['vm'])
    if args.get('reboot'):
        return GCPController().reboot_instance(args['projectID'], args['zone'], args['vm'])
    if args.get('delete'):
        return GCPController().delete_instance(args['projectID'], args['zone'], args['vm'])
    return True


def remote_controller(parent_args: list = None):
    args = ArgParser('KVM-2-GCP GCP Controller', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List instances',
            'action': 'store_true'
        },
        'vm': {
            'short': 'v',
            'help': 'Virtual machine name',
        },
        'projectID': {
            'short': 'p',
            'help': 'GCP project ID. Default: default',
            'default': 'default'
        },
        'zone': {
            'short': 'z',
            'help': 'GCP zone. Default: us-central1-a',
            'default': 'us-central1-a'
        },
        'delete': {
            'short': 'D',
            'help': 'Delete instance',
            'action': 'store_true'
        },
        'stop': {
            'short': 'S',
            'help': 'Stop instance',
            'action': 'store_true'
        },
        'start': {
            'short': 's',
            'help': 'Start instance',
            'action': 'store_true'
        },
        'reboot': {
            'short': 'R',
            'help': 'Reboot instance',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_remote_controller_args(args):
        exit(1)
    exit(0)

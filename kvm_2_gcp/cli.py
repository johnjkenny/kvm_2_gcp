from argparse import REMAINDER

from kvm_2_gcp.arg_parser import ArgParser


def parse_parent_args(args: dict):
    if args.get('controller'):
        return controller(args['controller'])
    if args.get('remoteImages'):
        return remote_images(args['remoteImages'])
    if args.get('images'):
        return images(args['images'])
    if args.get('deploy'):
        return deploy(args['deploy'])
    if args.get('init'):
        return init(args['init'])
    return True


def k2g_parent():
    args = ArgParser('KVM-2-GCP Commands', None, {
        'init': {
            'short': 'I',
            'help': 'Initialize KVM-2-GCP environment',
            'nargs': REMAINDER
        },
        'remoteImages': {
            'short': 'r',
            'help': 'Remote Images (k2g-remote-images)',
            'nargs': REMAINDER
        },
        'images': {
            'short': 'i',
            'help': 'Images (k2g-images)',
            'nargs': REMAINDER
        },
        'remoteDeploy': {},
        'deploy': {
            'short': 'd',
            'help': 'Deploy VM locally (KVM)',
            'nargs': REMAINDER
        },
        'build': {
            'short': 'b',
            'help': 'Build custom image and push to GCP',
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
        return Init(args['serviceAccount'], args['force']).run()
    return True


def init(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Initialization', parent_args, {
        'serviceAccount': {
            'short': 'sa',
            'help': 'Service account path (full path to json file)',
            'required': False,
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
    return True


def remote_images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Remote Images', parent_args, {
        'rocky': {
            'short': 'r',
            'help': 'Rocky family remote images (k2g-remote-rocky-images)',
            'nargs': REMAINDER
        },
        'ubuntu': {
            'short': 'u',
            'help': 'Ubuntu family remote images (k2g-remote-ubuntu-images)',
            'nargs': REMAINDER
        },
        'gcp': {
            'short': 'g',
            'help': 'GCP remote images',
            'nargs': REMAINDER
        },

        'project': {
            'short': 'p',
            'help': 'Project ID when pulling from cloud provider',
        },
        'family': {
            'short': 'f',
            'help': 'Image family when pulling from cloud provider',
        },
    }).set_arguments()
    if not parse_remote_image_args(args):
        exit(1)
    exit(0)


def parse_rocky_remote_image_args(args: dict):
    from kvm_2_gcp.remote_images import RockyImages
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
            'short': 'r',
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


def parse_image_args(args: dict):
    from kvm_2_gcp.kvm_images import KVMImages
    if args.get('list'):
        return KVMImages().list_images()
    if args.get('delete'):
        return KVMImages().delete_image(args['delete'], args['force'])
    return True


def images(parent_args: list = None):
    args = ArgParser('KVM-2-GCP Images', parent_args, {
        'list': {
            'short': 'l',
            'help': 'List images',
            'action': 'store_true'
        },
        'create': {
            'short': 'c',
            'help': 'Create image file of VM. Specify VM name',
        },
        'delete': {
            'short': 'D',
            'help': 'Delete image',
        },
        'force': {
            'short': 'F',
            'help': 'Force delete image',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_image_args(args):
        exit(1)
    exit(0)


def parse_deploy_args(args: dict):
    from kvm_2_gcp.kvm_deploy import KVMDeploy
    if args.get('image'):
        return KVMDeploy(args['name'], args['image'], args['cpu'], args['memory']).deploy()
    else:
        from kvm_2_gcp.kvm_images import KVMImages
        print('Image not specified. Please specify an image to deploy from the list below:')
        KVMImages().list_images()
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
    }).set_arguments()
    if not parse_deploy_args(args):
        exit(1)
    exit(0)


def parse_controller_args(args: dict):
    from kvm_2_gcp.kvm_controller import KVMController
    if args.get('list'):
        return KVMController().list_vms()
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
    if args.get('networks'):
        return network(args['vm'], args['networks'])
    if args.get('disks'):
        return disks(args['vm'], args['disks'])
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
    }).set_arguments()
    if not parse_controller_args(args):
        exit(1)
    exit(0)


def parse_network_args(vm_name: str, args: dict):
    from kvm_2_gcp.kvm_controller import KVMController
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
            'short': 'r',
            'help': 'Remove network interface from virtual machine (specify MAC address)',
        }
    }).set_arguments()
    if not parse_network_args(vm_name, args):
        exit(1)
    exit(0)


def parse_disk_args(vm_name: str, args: dict):
    from kvm_2_gcp.kvm_controller import KVMController
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
            'short': 'r',
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

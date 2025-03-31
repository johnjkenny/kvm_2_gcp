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
        'config': {
            'short': 'C',
            'help': 'Deploy using config file',
        },
        'force': {
            'short': 'F',
            'help': 'Force Delete Image',
            'action': 'store_true'
        },
    }).set_arguments()
    if not parse_deploy_args(args):
        exit(1)
    exit(0)


def parse_controller_args(args: dict):
    from kvm_2_gcp.kvm_controller import KVMController
    if args.get('start'):
        return KVMController().start_vm(args['start'])
    if args.get('stop'):
        return KVMController().shutdown_vm(args['stop'])
    if args.get('reboot'):
        return KVMController().reboot_vm(args['reboot'])
    if args.get('resetSoft'):
        return KVMController().soft_reset_vm(args['resetSoft'])
    if args.get('resetHard'):
        return KVMController().hard_reset_vm(args['resetHard'])
    if args.get('delete'):
        return KVMController().delete_vm(args['delete'])
    if args.get('list'):
        return KVMController().list_vms()
    if args.get('test'):
        return KVMController().run_tests()
    return True


def controller(parent_args: list = None):
    args = ArgParser('KVM-2-GCP KVM Controller', parent_args, {
        'delete': {
            'short': 'D',
            'help': 'Delete virtual machine'
        },
        'force': {
            'short': 'F',
            'action': 'store_true',
            'help': 'Force the action without prompting'
        },
        'list': {
            'short': 'l',
            'action': 'store_true',
            'help': 'List virtual machines'
        },
        'reboot': {
            'short': 'R',
            'help': 'Reboot virtual machine'
        },
        'resetHard': {
            'short': 'RH',
            'help': 'Reset virtual machine forcefully'
        },
        'resetSoft': {
            'short': 'RS',
            'help': 'Reset virtual machine gently'
        },
        'start': {
            'short': 's',
            'help': 'Start virtual machine'
        },
        'stop': {
            'short': 'S',
            'help': 'Stop virtual machine'
        },
    }).set_arguments()
    if not parse_controller_args(args):
        exit(1)
    exit(0)


'''
The difference between deploy and build:
deploy uses a specific instructions file to deploy the image

build uses the ansible name and uses ansible to build the system to playbooks


Demo example:

download rocky9.5 cloud image .qcow2
deploy the image using instructions file

build a custom image using ansible playbook

upload the image to gcp project images/bucket

deploy a gcp vm using the newly created image

'''

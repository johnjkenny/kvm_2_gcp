import getpass
from uuid import uuid4
from logging import Logger
from pathlib import Path

from google.cloud import compute_v1
from google.api_core.operation import Operation

from kvm_2_gcp.gcp_controller import GCPController
from kvm_2_gcp.remote_images import GCPImages


class GCPDeploy(GCPController):
    def __init__(self, name: str, image: str, image_project: str = 'default', disk_size: int = 10,
                 disk_type: str = 'pd-balanced', project_id: str = 'default', zone: str = 'us-central1-a',
                 machine_type: str = 'e2-highcpu-2', network_tags: list = ['ssh'], playbook: str = '',
                 add_user: bool = True, logger: Logger = None):
        super().__init__(logger=logger)
        self.project_id = project_id if project_id != 'default' else self._load_default_project_id()
        self._name = name if name != 'GENERATE' else f'vm-{uuid4().hex[:8]}'
        self._zone = zone
        self.__machine_type = machine_type
        self.__image = image
        self.__image_project_id = image_project if image_project != 'default' else self._load_default_project_id()
        self.__disk_size = disk_size
        self.__disk_type = disk_type
        self.__network_tags = network_tags
        self.__users = ['ansible']
        self._playbook = playbook or 'wait_for_startup_marker.yml'
        if add_user:
            user = getpass.getuser()
            if user == 'root':
                self.log.warning('Cannot use root user for SSH. Using default ansible user for SSH access')
            else:
                self.__users.append(user)

    @property
    def images(self):
        return GCPImages(self.__image_project_id)

    @property
    def __boot_initialize_params(self):
        image = self.images.get_image(self.__image)
        return compute_v1.AttachedDiskInitializeParams(
            source_image=image.self_link,
            disk_size_gb=self.__disk_size,
            disk_name=f'{self._name}-boot',
            disk_type=f'zones/{self._zone}/diskTypes/{self.__disk_type}'
        )

    @property
    def __boot_disk(self):
        return compute_v1.AttachedDisk(
            boot=True,
            auto_delete=True,
            device_name=f'{self._name}-boot',
            initialize_params=self.__boot_initialize_params
        )

    @property
    def __machine_type_path(self):
        return f'zones/{self._zone}/machineTypes/{self.__machine_type}'

    @property
    def __network_interface(self):
        return compute_v1.NetworkInterface(
            name='global/networks/default',
            access_configs=[compute_v1.AccessConfig(
                name='External NAT',
            )]
        )

    @property
    def __instance_sa(self):
        return compute_v1.ServiceAccount(
            email='default',
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

    @property
    def __meta_data(self):
        return compute_v1.Metadata(items=[
                compute_v1.Items(key='ssh-keys', value=self.__load_public_keys()),
                compute_v1.Items(key="startup-script", value=self.__load_startup_script()),
            ]
        )

    @property
    def __tags(self):
        return compute_v1.Tags(items=self.__network_tags)

    @property
    def __instance(self):
        return compute_v1.Instance(
            name=self._name,
            machine_type=self.__machine_type_path,
            disks=[self.__boot_disk],
            network_interfaces=[self.__network_interface],
            service_accounts=[self.__instance_sa],
            metadata=self.__meta_data,
            tags=self.__tags,
        )

    def __load_startup_script(self):
        try:
            with open(f'{self.template_dir}/default-startup.sh', 'r') as file:
                return file.read()
        except Exception:
            self.log.exception('Failed to load startup script')
            return ''

    def __load_public_key(self, public_key_file: str, user: str) -> str:
        try:
            with open(public_key_file, 'r') as f:
                public_key = f.read().strip()
                if f'{user}@' in public_key:
                    return public_key.split(f'{user}@')[0].strip() + f' {user}'
                return public_key
        except Exception:
            self.log.exception(f'Failed to get public key {public_key_file}')
        return ''

    def __load_public_keys(self) -> str:
        keys = []
        for user in self.__users:
            if user == 'ansible':
                keys.append(f'{user}:{self.__load_public_key(self.ansible_public_key, user)}')
            for key in ['id_rsa.pub', 'id_ed25519.pub']:
                pub_file = Path(f'/home/{user}/.ssh/{key}')
                if pub_file.exists():
                    keys.append(f'{user}:{self.__load_public_key(pub_file, user)}')
        return '\n'.join(keys)

    def __get_instance_ip(self, instance: compute_v1.Instance):
        for iface in instance.network_interfaces:
            if iface.access_configs:
                for access in iface.access_configs:
                    access: compute_v1.AccessConfig
                    if access.nat_i_p:
                        self.display_success_msg(f'Instance {self._name} created with external IP: {access.nat_i_p}')
                        self.is_port_open(access.nat_i_p, max_attempts=24)
                        return access.nat_i_p
        return None

    def __poll_operation(self, operation: Operation):
        if self._wait_for_zone_operation(operation, self._zone):
            instance = self.get_instance(self.project_id, self._zone, self._name)
            if instance:
                status = instance.status
                if status == 'RUNNING':
                    return self.__get_instance_ip(instance)
                if status in ['TERMINATED', 'STOPPING', 'STOPPED']:
                    self.log.error(f'Instance {self._name} failed to deploy: {status}')
                    return None
        return None

    def __display_vm_info(self, ip: str):
        users = ', '.join(self.__users)
        return self.display_success_msg(f'Successfully deployed VM {self._name} IP: {ip} User Access: {users}')

    def deploy(self):
        operation: Operation = self.create_instance(self.project_id, self._zone, self.__instance)
        if operation:
            ip = self.__poll_operation(operation)
            if ip and self.run_ansible_playbook(ip, self._name, self._playbook):
                return self.__display_vm_info(ip)
        return None

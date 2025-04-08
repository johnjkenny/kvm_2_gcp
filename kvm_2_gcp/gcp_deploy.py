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
        """Deploy a VM instance on GCP.

        Args:
            name (str): name of the instance
            image (str): image to use for the instance
            image_project (str, optional): the project the image resides in. Defaults to 'default'.
            disk_size (int, optional): size of boot disk in GB. Defaults to 10.
            disk_type (str, optional): boot disk perf type. Defaults to 'pd-balanced'.
            project_id (str, optional): project ID to deploy the VM in. Defaults to 'default'.
            zone (str, optional): zone to deploy the vm in. Defaults to 'us-central1-a'.
            machine_type (str, optional): machine type to deploy. Defaults to 'e2-highcpu-2' (2CPU, 2G RAM).
            network_tags (list, optional): network tags to allow FW traffic in. Defaults to ['ssh'].
            playbook (str, optional): ansible playbook to run to configure the system. Defaults to ''.
            add_user (bool, optional): option to add local user running the automation. Defaults to True.
            logger (Logger, optional): logger to use. Defaults to None.
        """
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
    def images(self) -> GCPImages:
        """GCP Image object to get image details.

        Returns:
            GCPImages: GCPImages object to get image details.
        """
        return GCPImages(self.__image_project_id)

    @property
    def __boot_initialize_params(self) -> compute_v1.AttachedDiskInitializeParams:
        """Create boot disk initialization parameters with disk size, image url, and disk type set.

        Returns:
            compute_v1.AttachedDiskInitializeParams: boot disk initialization parameters.
        """
        image = self.images.get_image(self.__image)
        return compute_v1.AttachedDiskInitializeParams(
            source_image=image.self_link,
            disk_size_gb=self.__disk_size,
            disk_name=f'{self._name}-boot',
            disk_type=f'zones/{self._zone}/diskTypes/{self.__disk_type}'
        )

    @property
    def __boot_disk(self) -> compute_v1.AttachedDisk:
        """Create boot disk object with auto-delete and boot set.

        Returns:
            compute_v1.AttachedDisk: boot disk object.
        """
        return compute_v1.AttachedDisk(
            boot=True,
            auto_delete=True,
            device_name=f'{self._name}-boot',
            initialize_params=self.__boot_initialize_params
        )

    @property
    def __machine_type_path(self) -> str:
        """Get the machine type path.

        Returns:
            str: machine type path with zone and machine type specified
        """
        return f'zones/{self._zone}/machineTypes/{self.__machine_type}'

    @property
    def __network_interface(self) -> compute_v1.NetworkInterface:
        """Create network interface object with default VPC and 1 external IP.

        Returns:
            compute_v1.NetworkInterface: network interface object.
        """
        return compute_v1.NetworkInterface(
            name='global/networks/default',
            access_configs=[compute_v1.AccessConfig(
                name='External NAT',
            )]
        )

    @property
    def __instance_sa(self) -> compute_v1.ServiceAccount:
        """Create service account object with default compute SA set

        Returns:
            compute_v1.ServiceAccount: service account object.
        """
        return compute_v1.ServiceAccount(
            email='default',
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

    @property
    def __meta_data(self) -> compute_v1.Metadata:
        """Create metadata object with ssh keys and startup script set

        Returns:
            compute_v1.Metadata: metadata object.
        """
        return compute_v1.Metadata(items=[
                compute_v1.Items(key='ssh-keys', value=self.__load_public_keys()),
                compute_v1.Items(key="startup-script", value=self.__load_startup_script()),
            ]
        )

    @property
    def __tags(self) -> compute_v1.Tags:
        """Create tags object with network tags set.

        Returns:
            compute_v1.Tags: tags object.
        """
        return compute_v1.Tags(items=self.__network_tags)

    @property
    def __instance(self) -> compute_v1.Instance:
        """Create instance object with name, machine type, disks, network interfaces, service accounts,
        metadata, and tags set.

        Returns:
            compute_v1.Instance: instance object to create
        """
        return compute_v1.Instance(
            name=self._name,
            machine_type=self.__machine_type_path,
            disks=[self.__boot_disk],
            network_interfaces=[self.__network_interface],
            service_accounts=[self.__instance_sa],
            metadata=self.__meta_data,
            tags=self.__tags,
        )

    def __load_startup_script(self) -> str:
        """Load the startup script from the template directory.

        Returns:
            str: startup script to run on instance creation.
        """
        try:
            with open(f'{self.template_dir}/gcp-startup.sh', 'r') as file:
                return file.read()
        except Exception:
            self.log.exception('Failed to load startup script')
            return ''

    def __load_public_key(self, public_key_file: str, user: str) -> str:
        """Load the public key from the file and return it in the format

        Args:
            public_key_file (str): path to the public key file
            user (str): user the key belongs to

        Returns:
            str: public key or empty string if failed to load
        """
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
        """Look up the public keys for the users specified in the __users list. Create a string with the format
        <user>:<public_key> for each user.

        Returns:
            str: string with the format <user>:<public_key> for each user
        """
        keys = []
        for user in self.__users:
            if user == 'ansible':
                keys.append(f'{user}:{self.__load_public_key(self.ansible_public_key, user)}')
            for key in ['id_rsa.pub', 'id_ed25519.pub']:
                pub_file = Path(f'/home/{user}/.ssh/{key}')
                if pub_file.exists():
                    keys.append(f'{user}:{self.__load_public_key(pub_file, user)}')
        return '\n'.join(keys)

    def __get_instance_ip(self, instance: compute_v1.Instance) -> str | None:
        """Get the external IP address of the instance from the network interfaces.

        Args:
            instance (compute_v1.Instance): instance object to get the IP from

        Returns:
            str: external IP address of the instance or None if not found
        """
        for iface in instance.network_interfaces:
            if iface.access_configs:
                for access in iface.access_configs:
                    access: compute_v1.AccessConfig
                    if access.nat_i_p:
                        self.display_success_msg(f'Instance {self._name} created with external IP: {access.nat_i_p}')
                        self.is_port_open(access.nat_i_p, max_attempts=24)
                        return access.nat_i_p
        return None

    def __poll_operation(self, operation: Operation) -> str | None:
        """Poll the operation to check if it is done and get the instance IP address on success

        Args:
            operation (Operation): operation object to poll

        Returns:
            str | None: external IP address of the instance or None if failed
        """
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

    def __display_vm_info(self, ip: str) -> bool:
        """Display the VM information after successful deployment.

        Args:
            ip (str): external IP address of the instance

        Returns:
            bool: True if successful, False otherwise
        """
        users = ', '.join(self.__users)
        return self.display_success_msg(f'Successfully deployed VM {self._name} IP: {ip} User Access: {users}')

    def deploy(self) -> str | None:
        """Deploy the VM instance on GCP and run the ansible playbook if specified.

        Returns:
            str | None: external IP address of the instance or None if failed
        """
        operation: Operation = self.create_instance(self.project_id, self._zone, self.__instance)
        if operation:
            ip = self.__poll_operation(operation)
            if ip and self.run_ansible_playbook(ip, self._name, self._playbook):
                return self.__display_vm_info(ip)
        return None

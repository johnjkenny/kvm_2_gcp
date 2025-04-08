import getpass
from pathlib import Path
from uuid import uuid4
from logging import Logger
from shutil import copy2

from yaml import safe_load, safe_dump

from kvm_2_gcp.utils import Utils
from kvm_2_gcp.kvm_controller import KVMController


class KVMDeploy(Utils):
    def __init__(self, name: str, image: str, disk_size: int = 10, cpu: int = 2, memory: int = 2048, playbook: str = '',
                 add_user: bool = True, logger: Logger = None):
        """Deploy a KVM using cloud-init and virt-install

        Args:
            name (str): name of the vm to deploy
            image (str): image to use for the vm
            disk_size (int, optional): size of boot disk in GB. Defaults to 10.
            cpu (int, optional): cpu qty to deploy. Defaults to 2.
            memory (int, optional): memory qty to deploy. Defaults to 2048.
            playbook (str, optional): ansible playbook to run to configure the system. Defaults to ''.
            add_user (bool, optional): option to add local user to system. Defaults to True.
            logger (Logger, optional): logger object to use. Defaults to None.
        """
        super().__init__(logger)
        if name == 'GENERATE':
            name = f'vm-{uuid4().hex[:8]}'
        self.__image = image
        self._name = name
        self.__disk_size = disk_size
        self.__cpu = cpu
        self.__memory = memory
        self.__deploy_dir = Path(f'{self.vm_dir}/{self._name}')
        self.__users = ['ansible']
        self.__startup = 'kvm-startup'
        self._playbook = playbook or 'wait_for_startup_marker.yml'
        if add_user:
            user = getpass.getuser()
            if user == 'root':
                self.log.warning('Cannot use root user for SSH. Using default ansible user for SSH access')
            else:
                self.__users.append(user)

    @property
    def controller(self) -> KVMController:
        """KVM controller object to use for KVM operations

        Returns:
            KVMController: KVM controller object
        """
        return KVMController(self.log)

    @property
    def __boot_disk(self) -> str:
        """Boot disk path for the VM

        Returns:
            str: boot disk path
        """
        return f'{self.__deploy_dir}/boot.{self.__image.split(".")[-1]}'

    @property
    def __iso_file(self) -> str:
        """CI-DATA ISO file path

        Returns:
            str: path to the CI-DATA ISO file
        """
        return f'{self.__deploy_dir}/cidata.iso'

    @property
    def __create_cmd(self) -> str:
        """Create the virt-install command to deploy the VM

        Returns:
            str: command to run to create the VM
        """
        return f'''virt-install \
--name={self._name} \
--os-variant=linux2022 \
--ram={self.__memory} \
--vcpus={self.__cpu} \
--import \
--disk path={self.__boot_disk},bus=scsi,serial={self._name}-boot,target=sda \
--disk path={self.__iso_file},device=cdrom,bus=scsi,serial={self._name}-cdrom,target=sdb \
--network bridge=virbr0,model=virtio \
--graphics vnc,listen=0.0.0.0 \
--noautoconsole'''

    def __create_user_cidata(self, user: str, public_key: str) -> dict:
        """Create the user data for the VM. Adds the users public key so they can ssh. Sets the user to sudo without
        password. Sets the default shell to /bin/bash

        Args:
            user (str): user to add to the VM
            public_key (str): public key for the user

        Returns:
            dict: user data for the VM
        """
        return {
            'name': user,
            'ssh_authorized_keys': [public_key],
            'sudo': 'ALL=(ALL) NOPASSWD:ALL',
            'groups': 'sudo',
            'shell': '/bin/bash'
        }

    def __load_public_key(self, public_key_file: str, user: str) -> str:
        """Load the public key from the file. If the host system is in the public key, remove it

        Args:
            public_key_file (str): path to the public key file
            user (str): user to add to the VM

        Returns:
            str: public key for the user
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

    def __get_user_public_keys(self, user: str) -> str:
        """Get the public key for the user. If the user is ansible, use the ansible public key. If the user is not
        then try to find the public key for the user using the default naming convention for RSA and ED25519 keys.

        Args:
            user (str): user to get the public key for

        Returns:
            str: public key for the user
        """
        if user == 'ansible':
            return self.__load_public_key(self.ansible_public_key, user)
        for key in ['id_rsa.pub', 'id_ed25519.pub']:
            pub_file = Path(f'/home/{user}/.ssh/{key}')
            if pub_file.exists():
                return self.__load_public_key(pub_file, user)
        self.log.warning(f'Failed to find public key for user {user}. Use default ansible user for SSH access')
        return ''

    def __create_vm_directory(self) -> bool:
        """Create the VM directory. This is where the boot disk and temp iso will be stored.

        Returns:
            bool: True if the directory was created, False if it already exists
        """
        if self.__deploy_dir.exists():
            self.log.error(f'VM directory {self.__deploy_dir} already exists')
            return False
        try:
            Path(f'{self.__deploy_dir}/iso').mkdir(parents=True)
            return True
        except Exception:
            self.log.exception(f'Failed to create VM directory {self.__deploy_dir}')
        return False

    def __load_user_cidata(self) -> dict:
        """Load the user data from the template file. This is used to set the user data for the VM and sets
        a default run_cmd schema to run a startup script.

        Returns:
            dict: user data for the VM
        """
        try:
            with open(f'{self.template_dir}/user-data.yml', 'r') as f:
                return safe_load(f)
        except Exception:
            self.log.exception('Failed to load user cidata')
        return {}

    def __save_user_cidata(self, cidata: dict) -> bool:
        """Save the user data to the VM directory. This is used to set the user data for cloud-init to pickup and
        generate. Data will be pulled into an ISO file and mounted to the VM via cdrom device

        Args:
            cidata (dict): user data for the VM

        Returns:
            bool: True if the data was saved, False otherwise
        """
        try:
            with open(f'{self.__deploy_dir}/iso/user-data', 'w') as f:
                f.write("#cloud-config\n\n")
                safe_dump(cidata, f, default_flow_style=False)
            return True
        except Exception:
            self.log.exception('Failed to set user cidata')
        return False

    def __set_user_cidata(self) -> bool:
        """Set the user data for the VM. This is used to set the user data for cloud-init to pickup and generate.

        Returns:
            bool: True if the data was set, False otherwise
        """
        cidata = self.__load_user_cidata()
        if cidata:
            for user in self.__users:
                cidata['users'].append(self.__create_user_cidata(user, self.__get_user_public_keys(user)))
            return self.__save_user_cidata(cidata)
        return False

    def __set_meta_cidata(self) -> bool:
        """Set the meta data for the VM. This is used to set the meta data for cloud-init to pickup and generate.
        This sets the hostname and instance ID for the VM to the name of the VM.

        Returns:
            bool: True if the data was set, False otherwise
        """
        try:
            with open(f'{self.template_dir}/meta-data.yml', 'r') as f:
                data = f.read()
            if data:
                data = data.replace('<VM_NAME>', self._name)
                with open(f'{self.__deploy_dir}/iso/meta-data', 'w') as f:
                    f.write(data)
                return True
            return False
        except Exception:
            self.log.exception('Failed to set meta cidata')
            return False

    def __set_startup_script(self) -> bool:
        """Set the startup script for the VM. This is bundled into the ISO file and user-data will run the script
        via cloud-init run_cmd.

        Returns:
            bool: True if the script was set, False otherwise
        """
        try:
            copy2(f'{self.template_dir}/{self.__startup}.sh', f'{self.__deploy_dir}/iso/startup.sh')
            return True
        except Exception:
            self.log.exception('Failed to set startup script')
            return False

    def __create_cidata_iso(self) -> bool:
        """Generate the ISO file for the VM. This is mounted to the VM via cdrom device. The ISO file will be deleted
        after a successful deploy

        Returns:
            bool: True if the ISO file was created, False otherwise
        """
        contents = []
        for file in self.__deploy_dir.glob('iso/*'):
            contents.append(f'{self.__deploy_dir}/iso/{file.name}')
        return self._run_cmd(f'genisoimage -output {self.__iso_file} -V cidata -r -J {" ".join(contents)}')[1]

    def __create_vm_boot_disk(self) -> bool:
        """Copies the image file to the VM directory and sets the disk size.

        Returns:
            bool: True if the disk was created, False otherwise
        """
        image_file = Path(f'{self.image_dir}/{self.__image}')
        if image_file.exists():
            try:
                copy2(image_file, self.__boot_disk)
            except Exception:
                self.log.exception(f'Failed to create VM {self._name} boot disk')
                return False
            if self.__disk_size > 10:
                return self.controller.set_disk_size(self._name, self.__boot_disk, f'{self.__disk_size}GB', True)
            return True
        else:
            self.log.error(f'Image {self.__image} not found')
        return False

    def __cleanup_iso_data(self) -> bool:
        """Cleanup the deploy data which includes the ISO file and the tem directory to create the ISO file.

        Returns:
            bool: True if the cleanup was successful, False otherwise
        """
        for delete in ['cidata.iso', 'iso']:
            if not self._run_cmd(f'rm -rf {self.__deploy_dir}/{delete}')[1]:
                return False
        return True

    def __display_vm_info(self, ip: str) -> bool:
        """Display the VM information after a successful deploy. This includes the IP address and the users that have
        access to the VM.

        Args:
            ip (str): IP address of the VM

        Returns:
            bool: True if the information was displayed, False otherwise
        """
        users = ', '.join(self.__users)
        return self.display_success_msg(f'Successfully deployed VM {self._name} IP: {ip} User Access: {users}')

    def __create_vm(self) -> bool:
        """Create the VM using the virt-install command. Poll to get the VM ip address, then wait for port 22 to be
        open. Next, run an ansible playbook then eject the ISO file, remove the cdrom device and cleanup the ISO data.
        Display the VM information after a successful deploy.

        Returns:
            bool: True if the VM was created, False otherwise
        """
        if self._run_cmd(self.__create_cmd)[1]:
            ip = self.controller._wait_for_vm_init(self._name)
            if ip and self.is_port_open(ip) and self.run_ansible_playbook(ip, self._name, self._playbook):
                if self.controller.eject_instance_iso(self._name, True):
                    return self.__cleanup_iso_data() and self.__display_vm_info(ip)
        return False

    def deploy(self) -> bool:
        """Deploy the VM using the virt-install command. This will create the VM directory, boot disk, user data,
        meta data, startup script, CI-DATA ISO file and finally create the VM using the virt-install command.

        Returns:
            bool: _description_
        """
        for method in [self.__create_vm_directory, self.__create_vm_boot_disk, self.__set_user_cidata,
                       self.__set_meta_cidata, self.__set_startup_script, self.__create_cidata_iso, self.__create_vm]:
            if not method():
                self.log.error(f'Failed to deploy VM {self._name}')
                return False
        return True

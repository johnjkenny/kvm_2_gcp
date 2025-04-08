import getpass
from pathlib import Path
from platform import freedesktop_os_release
from shutil import which, copytree
from json import dump

from kvm_2_gcp.utils import Utils


class Init(Utils):
    def __init__(self, sa_path: str, default_bucket: str = '', force: bool = False):
        """Initialize the KVM-2-GCP environment by setting up the service account and project ID.
        This class also creates the necessary SSH keys for Ansible.

        Args:
            sa_path (str): Path to the service account JSON file
            force (bool, optional): force action. Defaults to False.

        Raises:
            FileNotFoundError: if the service account file does not exist
        """
        super().__init__()
        self.__sa_path = sa_path
        if not Path(sa_path).exists():
            raise FileNotFoundError(f'File not found: {sa_path}')
        self.__default_bucket = default_bucket
        self.__force = force
        self.__group = ''

    def __install_kvm_dependencies(self) -> bool:
        os_id = freedesktop_os_release().get('ID_LIKE').lower()
        if 'debian' in os_id:
            self.__group = 'kvm'
            pkgs = 'qemu-kvm libvirt-daemon-system libvirt-clients virtinst bridge-utils genisoimage'
            return self._run_cmd(f'sudo apt install -y {pkgs}')[1]
        if 'rhel' in os_id:
            self.__group = 'qemu'
            pkgs = 'qemu-kvm libvirt virt-install libvirt-daemon-config-network libvirt-daemon-kvm bridge-utils'
            if which('dnf'):
                return self._run_cmd(f'sudo dnf install -y {pkgs} genisoimage')[1]
            if which('yum'):
                return self._run_cmd(f'sudo yum install -y {pkgs} genisoimage')[1]
            self.log.error(f'Unable to find package manager for RHEL based system: {os_id}')
        else:
            self.log.error(f'Unsupported OS: {os_id}')
        return False

    def __start_and_enable_libvirt(self) -> bool:
        return self._run_cmd('sudo systemctl enable --now libvirtd')[1]

    def __set_directory_permissions(self) -> bool:
        user = getpass.getuser()
        if not self._run_cmd('sudo mkdir -p /k2g')[1]:
            return False
        for cmd in [f'chown -R {user}:{self.__group}', 'chmod -R 2770', 'setfacl -d -m u::rwx', 'setfacl -d -m g::rwx',
                    'setfacl -d -m o::0']:
            if not self._run_cmd(f'sudo {cmd} /k2g')[1]:
                return False
        return self.__set_user_to_libvirt_group(user) and self.__set_directory_structure()

    def __set_user_to_libvirt_group(self, user: str) -> bool:
        for cmd in [f'usermod -aG libvirt {user}']:
            if not self._run_cmd(f'sudo {cmd}')[1]:
                return False
        return True

    def __set_directory_structure(self) -> bool:
        for _dir in [self.image_dir, self.vm_dir, self.ansible_clients, self.ansible_playbooks, self.env_dir]:
            if not self._run_cmd(f'mkdir -p {_dir}')[1]:
                return False
        return True

    def __create_env_key(self) -> bool:
        """Create the cipher key for encryption/decryption

        Returns:
            bool: True if the key was created successfully, False otherwise
        """
        if self.__force or not Path(self.cipher.key_file).exists():
            return self.cipher._create_key()
        return True

    def __set_default_service_account(self) -> bool:
        """Set the default service account

        Returns:
            bool: True if the service account was set successfully, False otherwise
        """
        try:
            with open(self.default_sa, 'w') as file:
                file.write(self.service_account)
            return True
        except Exception:
            self.log.exception('Failed to set default service account')
        return False

    def __set_default_project_id(self) -> bool:
        """Set the default project ID

        Returns:
            bool: True if the project ID was set successfully, False otherwise
        """
        try:
            with open(self.default_project_id, 'w') as file:
                file.write(self.project_id)
            return True
        except Exception:
            self.log.exception('Failed to set default project ID')
        return False

    def __create_credentials(self) -> bool:
        """Create the service account file and encrypt it with the cipher key

        Returns:
            bool: True if the service account file was created successfully, False otherwise
        """
        sa = self._load_json_service_account(self.__sa_path)
        if sa:
            self.service_account = sa.get('client_email', '').split('@')[0]
            self.project_id = sa.get('project_id', '')
            if self.__force or not Path(self.default_sa).exists():
                if not self.__set_default_service_account():
                    return False
            if self.__force or not Path(self.default_project_id).exists():
                if not self.__set_default_project_id():
                    return False
            if self.__force or not Path(self.sa_file).exists():
                return self._create_service_account_file(self.sa_file, sa)
            self.log.info('Credentials file already exists. Use --force to overwrite if needed')
            return True
        return False

    def __create_default_bucket_files(self) -> bool:
        """Create the default bucket files

        Returns:
            bool: True if the bucket files were created successfully, False otherwise
        """
        if self.__force or not Path(self.default_bucket).exists():
            try:
                with open(self.default_bucket, 'w') as file:
                    file.write(self.__default_bucket)
            except Exception:
                self.log.exception('Failed to set default bucket')
                return False
        if self.__force or not Path(self.used_buckets_file).exists():
            try:
                with open(self.used_buckets_file, 'w') as file:
                    dump([self.__default_bucket], file)
                    file.write('\n')
            except Exception:
                self.log.exception('Failed to set default bucket')
                return False
        return True

    def __create_ansible_files(self):
        """Create the Ansible files

        Returns:
            bool: True if the Ansible files were created successfully, False otherwise
        """
        try:
            copytree(f'{Path(__file__).parent}/ansible', self.ansible_dir, dirs_exist_ok=True)
            return True
        except Exception:
            self.log.exception('Failed to create Ansible files')
            return False

    def __create_ansible_ssh_keys(self) -> bool:
        """Create SSH keys for Ansible to use to connect to VM instances

        Returns:
            bool: True on success, False otherwise
        """
        if Path(self.ansible_private_key).exists():
            if self.__force:
                if not self._run_cmd(f'rm -f {self.ansible_private_key}*')[1]:
                    return False
            else:
                return True
        if self._run_cmd(f'ssh-keygen -t rsa -b 4096 -C "ansible" -f {self.ansible_private_key} -N ""')[1]:
            return self._run_cmd(f'chmod 600 {self.ansible_private_key}')[1]
        return False

    def run(self) -> bool:
        """Run the initialization process for GCP IaC

        Returns:
            bool: True on success, False otherwise
        """
        for method in [self.__install_kvm_dependencies, self.__start_and_enable_libvirt,
                       self.__set_directory_permissions, self.__create_env_key, self.__create_credentials,
                       self.__create_default_bucket_files, self.__create_ansible_files, self.__create_ansible_ssh_keys]:
            if not method():
                return False
        self.log.info('Successfully initialized KVM-2-GCP Environment')
        return True

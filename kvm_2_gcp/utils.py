import json
import pickle
import socket
from logging import Logger
from subprocess import run
from pathlib import Path
from time import sleep

import ansible_runner
from google.oauth2 import service_account

from kvm_2_gcp.logger import get_logger
from kvm_2_gcp.color import Color
from kvm_2_gcp.encrypt import Cipher


class Utils():
    def __init__(self, service_account: str = 'default', project_id: str = '', logger: Logger = None):
        self.log = logger or get_logger('kvm-2-gcp')
        self.service_account = service_account
        self.project_id = project_id

    @property
    def cipher(self):
        """Cipher object for encryption/decryption

        Returns:
            Cipher: Cipher object
        """
        return Cipher(self.log)

    @property
    def image_dir(self):
        return '/k2g/images'

    @property
    def vm_dir(self):
        return '/k2g/vms'

    @property
    def snapshot_dir(self):
        return '/k2g/snapshots'

    @property
    def config_dir(self):
        return '/k2g/config'

    @property
    def template_dir(self):
        return f'{Path(__file__).parent}/templates'

    @property
    def ansible_private_key(self):
        return f'{Path(__file__).parent}/k2g_env/keys/.ansible_rsa'

    @property
    def ansible_public_key(self):
        return self.ansible_private_key + '.pub'

    @property
    def ansible_dir(self) -> str:
        """Get the path to the Ansible directory

        Returns:
            str: Path to the Ansible directory
        """
        return f'{Path(__file__).parent}/ansible'

    @property
    def ansible_env_vars(self) -> dict:
        """Get Ansible environment variables

        Returns:
            dict: Ansible environment variables
        """
        return {
            'ANSIBLE_CONFIG': f'{self.ansible_dir}/ansible.cfg',
            'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3',
            'ANSIBLE_PRIVATE_KEY_FILE': self.ansible_private_key,
        }

    @property
    def default_sa(self) -> str:
        """Get the default service account file path

        Returns:
            str: default service account file path
        """
        return f'{Path(__file__).parent}/k2g_env/default_sa'

    @property
    def default_project_id(self) -> str:
        """Get the default project ID

        Returns:
            str: default project ID
        """
        return f'{Path(__file__).parent}/k2g_env/default_project_id'

    @property
    def sa_file(self) -> str:
        """Get the service account file path. Looks up default service account if 'default' is set

        Returns:
            str: service account file path
        """
        if self.service_account == 'default':
            self.service_account = self.__get_default_service_account()
        return f'{Path(__file__).parent}/k2g_env/keys/.{self.service_account}.sa'

    @property
    def creds(self) -> service_account.Credentials | None:
        """Get the service account credentials object. Sets the project ID if not set

        Returns:
            service_account.Credentials | None: service account credentials object or None on failure
        """
        try:
            with open(self.sa_file, 'rb') as file:
                __creds: dict = pickle.loads(self.cipher.decrypt(file.read(), self.cipher.load_key()))
            if not self.project_id:
                self.project_id = __creds.get('project_id', '')
            return service_account.Credentials.from_service_account_info(__creds)
        except Exception:
            self.log.exception('Failed to load credentials')
        return None

    @staticmethod
    def display_success_msg(msg: str):
        """Display success message

        Args:
            msg (str): message to display
        """
        Color().print_message(msg, 'green')
        return True

    @staticmethod
    def display_warning_msg(msg: str):
        """Display warning message

        Args:
            msg (str): message to display
        """
        Color().print_message(msg, 'yellow')
        return True

    @staticmethod
    def display_info_msg(msg: str):
        """Display info message

        Args:
            msg (str): message to display
        """
        Color().print_message(msg, 'cyan')
        return True

    @staticmethod
    def display_fail_msg(msg: str):
        """Display fail message

        Args:
            msg (str): message to display
        """
        Color().print_message(msg, 'red')
        return False

    def __get_default_service_account(self) -> str:
        """Get the default service account name

        Returns:
            str: default service account name or empty string if failed
        """
        try:
            with open(self.default_sa, 'r') as file:
                return file.read().strip()
        except Exception:
            self.log.exception('Failed to load default service account')
        return ''

    def _run_cmd(self, cmd: str, ignore_error: bool = False, log_output: bool = False) -> tuple:
        """Run a command and return the output

        Args:
            cmd (str): Command to run
            ignore_error (bool, optional): ignore errors. Defaults to False
            log_output (bool, optional): Log command output. Defaults to False.

        Returns:
            tuple: (stdout, True. '') on success or (stdout, False, error) on failure
        """
        state = True
        error = ''
        output = run(cmd, shell=True, capture_output=True, text=True)
        if output.returncode != 0:
            state = False
            error = output.stderr
            if not ignore_error:
                self.log.error(f'Command: {cmd}\nExit Code: {output.returncode}\nError: {error}')
                return '', state, error
        stdout = output.stdout
        if log_output:
            self.log.info(f'Command: {cmd}\nOutput: {stdout}')
        return stdout, state, error

    def _create_service_account_file(self, sa_file: str, sa_data: dict) -> bool:
        """Create a service account file and encrypt it with the cipher key.

        Args:
            sa_file (str): path to the service account file
            sa_data (dict): service account data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(sa_file, 'wb') as file:
                file.write(self.cipher.encrypt(pickle.dumps(sa_data), self.cipher.load_key()))
            return True
        except Exception:
            self.log.exception('Failed to create service account file')
        return False

    def _load_json_service_account(self, sa_path: str) -> dict:
        """Load a service account json file to a dictionary

        Args:
            sa_path (str): path to the service account json file

        Returns:
            dict: service account data
        """
        try:
            with open(sa_path, 'r') as sa_file:
                return json.load(sa_file)
        except Exception:
            self.log.exception('Failed to create credentials file')
        return {}

    def _load_default_project_id(self):
        try:
            with open(self.default_project_id, 'r') as f:
                return f.read().strip()
        except Exception:
            self.log.exception('Failed to get default project ID')
        return ''

    def __create_ansible_client_directory(self, client_dir: Path, name: str, ip: str) -> bool:
        """Create the Ansible client directory and inventory file

        Args:
            client_dir (Path): Path to the client directory
            ip (str): client IP address

        Returns:
            bool: True on success, False otherwise
        """
        try:
            Path.mkdir(client_dir, parents=True, exist_ok=True)
            data = f"[all]\n{name} ansible_host={ip}\n"
            with open(f'{client_dir}/inventory.ini', 'w') as f:
                f.write(data)
            return True
        except Exception:
            self.log.exception('Failed to create client directory')
            return False

    def is_port_open(self, ip: str, port: int = 22, timeout: int = 5, max_attempts: int = 12) -> bool:
        """Check if a port is open on a given IP address. Will check for 1 minute before giving up with the default
        timeout and max attempts set.

        Args:
            ip (str): ip address to check
            port (int, optional): port to check. Defaults to 22.
            timeout (int, optional): timeout between checks. Defaults to 5.
            max_attempts (int, optional): max attempts before giving up. Defaults to 12

        Returns:
            bool: True if the port is open, False otherwise
        """
        self.display_info_msg(f'Waiting for {ip}:{port} to be open')
        while max_attempts > 0:
            try:
                with socket.create_connection((ip, port), timeout=timeout):
                    self.display_success_msg(f'{ip}:{port} is open, running Ansible playbook')
                    return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                self.display_warning_msg(f'{ip}:{port} is not open. Retrying in {timeout} seconds')
                sleep(timeout)
                max_attempts -= 1
                continue
        self.display_fail_msg('Failed to determine if port is open')
        return False

    def run_ansible_playbook(self, ip: str, name: str, playbook: str, extravars: dict = None) -> bool:
        """Run the Ansible playbook to configure the VM. This will configure the VM with Docker and deploy app1

        Args:
            ip (str): IP address of the VM
            name (str): name of the VM

        Returns:
            bool: True on success, False otherwise
        """
        client_dir = Path(f'{self.ansible_dir}/clients/{name}')
        self.__create_ansible_client_directory(client_dir, name, ip)
        result = ansible_runner.run(
            private_data_dir=client_dir.absolute(),
            playbook=f'{self.ansible_dir}/playbooks/{playbook}',
            inventory=f'{client_dir}/inventory.ini',
            artifact_dir=f'{client_dir}/artifacts',
            envvars=self.ansible_env_vars,
            extravars=extravars)
        if result.rc == 0:
            return True
        self.log.error(f'Failed to run Ansible playbook: {result.status}')
        return False

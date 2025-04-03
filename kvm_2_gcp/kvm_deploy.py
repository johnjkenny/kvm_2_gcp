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
        self.__startup = 'default-startup'
        self._playbook = playbook or 'wait_for_startup_marker.yml'
        if add_user:
            user = getpass.getuser()
            if user == 'root':
                self.log.warning('Cannot use root user for SSH. Using default ansible user for SSH access')
            else:
                self.__users.append(user)

    @property
    def controller(self):
        return KVMController(self.log)

    @property
    def __boot_disk(self):
        return f'{self.__deploy_dir}/boot.{self.__image.split(".")[-1]}'

    @property
    def __iso_file(self):
        return f'{self.__deploy_dir}/cidata.iso'

    @property
    def __create_cmd(self):
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

    def __create_user_cidata(self, user: str, public_key: str):
        return {
            'name': user,
            'ssh_authorized_keys': [public_key],
            'sudo': 'ALL=(ALL) NOPASSWD:ALL',
            'groups': 'sudo',
            'shell': '/bin/bash'
        }

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

    def __get_user_public_keys(self, user: str) -> str:
        if user == 'ansible':
            return self.__load_public_key(self.ansible_public_key, user)
        for key in ['id_rsa.pub', 'id_ed25519.pub']:
            pub_file = Path(f'/home/{user}/.ssh/{key}')
            if pub_file.exists():
                return self.__load_public_key(pub_file, user)
        self.log.warning(f'Failed to find public key for user {user}. Use default ansible user for SSH access')
        return ''

    def __create_vm_directory(self):
        if self.__deploy_dir.exists():
            self.log.error(f'VM directory {self.__deploy_dir} already exists')
            return False
        try:
            Path(f'{self.__deploy_dir}/iso').mkdir(parents=True)
            Path(f'{self.__deploy_dir}/ansible').mkdir()
            return True
        except Exception:
            self.log.exception(f'Failed to create VM directory {self.__deploy_dir}')
        return False

    def __load_user_cidata(self) -> dict:
        try:
            with open(f'{self.template_dir}/user-data.yml', 'r') as f:
                return safe_load(f)
        except Exception:
            self.log.exception('Failed to load user cidata')
        return {}

    def __save_user_cidata(self, cidata: dict):
        try:
            with open(f'{self.__deploy_dir}/iso/user-data', 'w') as f:
                f.write("#cloud-config\n\n")
                safe_dump(cidata, f, default_flow_style=False)
            return True
        except Exception:
            self.log.exception('Failed to set user cidata')
        return False

    def __set_user_cidata(self):
        cidata = self.__load_user_cidata()
        if cidata:
            for user in self.__users:
                cidata['users'].append(self.__create_user_cidata(user, self.__get_user_public_keys(user)))
            return self.__save_user_cidata(cidata)
        return False

    def __set_meta_cidata(self):
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

    def __set_startup_script(self):
        try:
            copy2(f'{self.template_dir}/{self.__startup}.sh', f'{self.__deploy_dir}/iso/startup.sh')
            return True
        except Exception:
            self.log.exception('Failed to set startup script')
            return False

    def __create_cidata_iso(self):
        contents = []
        for file in self.__deploy_dir.glob('iso/*'):
            contents.append(f'{self.__deploy_dir}/iso/{file.name}')
        return self._run_cmd(f'genisoimage -output {self.__iso_file} -V cidata -r -J {" ".join(contents)}')[1]

    def __create_vm_boot_disk(self):
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

    def __cleanup_iso_data(self):
        for delete in ['cidata.iso', 'iso']:
            if not self._run_cmd(f'rm -rf {self.__deploy_dir}/{delete}')[1]:
                return False
        return True

    def __display_vm_info(self, ip: str):
        users = ', '.join(self.__users)
        return self.display_success_msg(f'Successfully deployed VM {self._name} IP: {ip} User Access: {users}')

    def __create_vm(self):
        if self._run_cmd(self.__create_cmd)[1]:
            ip = self.controller._wait_for_vm_init(self._name)
            if ip and self.is_port_open(ip) and self.run_ansible_playbook(ip, self._name, self._playbook):
                if self.controller.eject_instance_iso(self._name, True):
                    return self.__cleanup_iso_data() and self.__display_vm_info(ip)
        return False

    def deploy(self):
        for method in [self.__create_vm_directory, self.__create_vm_boot_disk, self.__set_user_cidata,
                       self.__set_meta_cidata, self.__set_startup_script, self.__create_cidata_iso, self.__create_vm]:
            if not method():
                self.log.error(f'Failed to deploy VM {self._name}')
                return False
        return True

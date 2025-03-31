import getpass
from pathlib import Path
from uuid import uuid4
from logging import Logger
from shutil import copy2

from kvm_2_gcp.utils import Utils


class KVMDeploy(Utils):
    def __init__(self, name: str, image: str, cpu: int = 2, memory: int = 2048, is_build: bool = False,
                 logger: Logger = None):
        super().__init__(logger)
        if name == 'GENERATE':
            name = f'vm-{uuid4().hex[:8]}'
        self.__image = image
        self.__name = name
        self.__cpu = cpu
        self.__memory = memory
        self.__deploy_dir = Path(f'{self.vm_dir}/{self.__name}')
        if is_build:
            self.__user = 'ansible'
            self.__startup = 'build-startup'
        else:
            self.__user = getpass.getuser()
            self.__startup = 'default-startup'
            if self.__user == 'root':
                self.log.warning('Cannot use root user for image. Using default ansible user')
                self.__user = 'ansible'

    @property
    def __boot_disk(self):
        return f'{self.__deploy_dir}/boot.{self.__image.split(".")[-1]}'

    @property
    def __iso_file(self):
        return f'{self.__deploy_dir}/cidata.iso'

    @property
    def __create_cmd(self):
        return f'''virt-install \
--name={self.__name} \
--osinfo=detect=on,require=off \
--ram={self.__memory} \
--vcpus={self.__cpu} \
--import \
--disk path={self.__boot_disk},bus=scsi,serial={self.__name}-boot,target=sda \
--disk path={self.__iso_file},device=cdrom,bus=scsi,serial={self.__name}-cdrom \
--network bridge=virbr0,model=virtio \
--graphics vnc,listen=0.0.0.0 \
--noautoconsole'''

    def __load_public_key(self, public_key_file: str):
        try:
            with open(public_key_file, 'r') as f:
                public_key = f.read().strip()
                if f'{self.__user}@' in public_key:
                    return public_key.split(f'{self.__user}@')[0].strip() + f' {self.__user}'
                return public_key
        except Exception:
            self.log.exception(f'Failed to get public key {public_key_file}')
        return ''

    def __get_user_public_key(self):
        if self.__user == 'ansible':
            return self.__load_public_key(self.ansible_public_key)
        for key in ['id_rsa.pub', 'id_ed25519.pub']:
            pub_file = Path(f'/home/{self.__user}/.ssh/{key}')
            if pub_file.exists():
                return self.__load_public_key(pub_file)
        self.log.info(f'Failed to find public key for user {self.__user}. Using default ansible user')
        self.__user = 'ansible'
        return self.__load_public_key(self.ansible_public_key)

    def __create_vm_directory(self):
        if self.__deploy_dir.exists():
            self.log.error(f'VM directory {self.__deploy_dir} already exists')
            return False
        try:
            Path(f'{self.__deploy_dir}/iso').mkdir(parents=True)
            return True
        except Exception:
            self.log.exception(f'Failed to create VM directory {self.__deploy_dir}')
        return False

    def __set_user_cidata(self):
        public_key_data = self.__get_user_public_key()
        if public_key_data:
            try:
                with open(f'{self.template_dir}/user-data.yml', 'r') as f:
                    data = f.read()
                if data:
                    data = data.replace('<USER>', self.__user).replace('<PUBLIC_KEY>', public_key_data)
                    with open(f'{self.__deploy_dir}/iso/user-data', 'w') as f:
                        f.write(data)
                    return True
                return False
            except Exception:
                self.log.exception('Failed to set user cidata')
        return False

    def __set_meta_cidata(self):
        try:
            with open(f'{self.template_dir}/meta-data.yml', 'r') as f:
                data = f.read()
            if data:
                data = data.replace('<VM_NAME>', self.__name)
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
                return True
            except Exception:
                self.log.exception(f'Failed to create VM {self.__name} boot disk')
        else:
            self.log.error(f'Image {self.__image} not found')
        return False

    def __create_vm(self):
        # ToDo: Add handling for vm startup script to be complete, run ansible if build is true
        # clean up the build directory - eject the iso, delete the iso dir and delete the iso file
        return self._run_cmd(self.__create_cmd)[1]

    def deploy(self):
        for method in [self.__create_vm_directory, self.__create_vm_boot_disk, self.__set_user_cidata,
                       self.__set_meta_cidata, self.__set_startup_script, self.__create_cidata_iso, self.__create_vm]:
            if not method():
                self.log.error(f'Failed to deploy VM {self.__name}: {method.__name__}')
                return False
        # ToDO: Display VM info, IP, name, user, etc
        return True

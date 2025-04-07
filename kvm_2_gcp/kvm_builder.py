from datetime import datetime
from pathlib import Path
from logging import Logger

from kvm_2_gcp.kvm_deploy import KVMDeploy
from kvm_2_gcp.kvm_images import KVMImages


class KVMBuilder(KVMDeploy):
    def __init__(self, name: str = 'GENERATE', image: str = '', disk_size: int = 10, cpu: int = 2, memory: int = 2048,
                 playbook: str = '', logger: Logger = None):
        name = name if name != 'GENERATE' else f'build-{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'
        playbook = f'builds/{playbook}' if playbook else ''
        super().__init__(name, image, disk_size, cpu, memory, playbook, False, logger)

    @property
    def __build_dir(self):
        return f'{self.ansible_dir}/playbooks/builds'

    @property
    def images(self):
        return KVMImages(self.log)

    def display_build_options(self):
        builds = []
        for content in Path(self.__build_dir).glob('*.yml'):
            builds.append(content.name)
        builds.sort()
        return self.display_info_msg(f'Available builds:\n  {"\n  ".join(builds)}')

    def __run_build_playbook(self):
        ip = self.controller.get_vm_ip_by_interface_name(self._name)
        if ip:
            return self.run_ansible_playbook(ip, self._name, self._playbook)
        self.log.error(f'Unable to get IP for {self._name}')
        return False

    def run_build(self):
        if self._name in self.controller.get_running_instances() and not self.__run_build_playbook():
            self.log.error(f'Failed to build image {self._name}.qcow2')
            return False
        else:
            if not self.deploy():
                self.log.error(f'Failed to build image {self._name}.qcow2')
                return False
        if self.images.create_clone(self._name, self._name, True) and self.controller.delete_vm(self._name, True):
            self.log.info(f'Successfully built image {self._name}.qcow2')
            return True
        self.log.error(f'Failed to build image {self._name}.qcow2')
        return False

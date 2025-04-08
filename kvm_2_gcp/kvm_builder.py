from datetime import datetime
from pathlib import Path
from logging import Logger

from kvm_2_gcp.kvm_deploy import KVMDeploy
from kvm_2_gcp.kvm_images import KVMImages


class KVMBuilder(KVMDeploy):
    def __init__(self, name: str = 'GENERATE', image: str = '', disk_size: int = 10, cpu: int = 2, memory: int = 2048,
                 playbook: str = '', logger: Logger = None):
        """Create a custom KVM image using Ansible playbook to configure the VM

        Args:
            name (str, optional): name to name the build VM. Defaults to 'GENERATE'.
            image (str, optional): image to use for the deployment. Defaults to ''.
            disk_size (int, optional): size of the boot disk. Defaults to 10.
            cpu (int, optional): cpu qty for the deployment. Defaults to 2.
            memory (int, optional): memory amount for deployment. Defaults to 2048.
            playbook (str, optional): build playbook to run to configure the system. Defaults to ''.
            logger (Logger, optional): logger to use. Defaults to None.
        """
        name = name if name != 'GENERATE' else f'build-{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'
        playbook = f'builds/{playbook}' if playbook else ''
        super().__init__(name, image, disk_size, cpu, memory, playbook, False, logger)

    @property
    def __build_dir(self) -> str:
        """Directory where the build playbooks are stored

        Returns:
            str: directory where the build playbooks are stored
        """
        return f'{self.ansible_dir}/playbooks/builds'

    @property
    def images(self) -> KVMImages:
        """KVM images object to handle image creation and management

        Returns:
            KVMImages: KVM images object
        """
        return KVMImages(self.log)

    def display_build_options(self) -> bool:
        """Display the available build options

        Returns:
            bool: True if the build options were displayed successfully, False otherwise
        """
        builds = []
        for content in Path(self.__build_dir).glob('*.yml'):
            builds.append(content.name)
        builds.sort()
        return self.display_info_msg(f'Available builds:\n  {"\n  ".join(builds)}')

    def __run_build_playbook(self) -> bool:
        """Run the build playbook to configure the VM

        Returns:
            bool: True if the playbook was run successfully, False otherwise
        """
        ip = self.controller.get_vm_ip_by_index(self._name)
        if ip:
            return self.run_ansible_playbook(ip, self._name, self._playbook)
        self.log.error(f'Unable to get IP for {self._name}')
        return False

    def run_build(self) -> bool:
        """Run the build process to create a custom KVM image. Will rerun the ansible playbook if the name provided
        already exists and is running. Will create a VM, run the playbook, powers down the VM, then creates a
        clone of the VM to create the image. The VM is then deleted.

        Returns:
            bool: True if the build was successful, False otherwise
        """
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

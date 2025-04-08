from datetime import datetime
from pathlib import Path
from logging import Logger

from kvm_2_gcp.gcp_deploy import GCPDeploy
from kvm_2_gcp.remote_images import GCPImages


class GCPBuilder(GCPDeploy):
    def __init__(self, name: str = 'GENERATE', image: str = 'GENERATE', image_project: str = 'default',
                 disk_size: int = 10, disk_type: str = 'pd-balanced', project_id: str = 'default',
                 zone: str = 'us-central1-a', machine_type: str = 'e2-highcpu-2', network_tags: list = ['ssh'],
                 playbook: str = '', family: str = 'k2g-images', logger: Logger = None):
        """Create a GCP image by deploying a VM in GCP and running a build playbook to configure the system

        Args:
            name (str, optional): name of the build vm. Defaults to 'GENERATE'.
            image (str, optional): name to call the image file after build. Defaults to 'GENERATE'.
            image_project (str, optional): project to store the image file. Defaults to 'default'.
            disk_size (int, optional): size of the VM boot disk. Defaults to 10.
            disk_type (str, optional): GCP boot disk type. Defaults to 'pd-balanced'.
            project_id (str, optional): project ID to deploy the build VM in. Defaults to 'default'.
            zone (str, optional): zone to deploy the VM in. Defaults to 'us-central1-a'.
            machine_type (str, optional): Machine type to deploy the VM. Defaults to 'e2-highcpu-2 (2CPU, 2G RAM)'.
            network_tags (list, optional): network tags to add to the VM to allow FW traffic. Defaults to ['ssh'].
            playbook (str, optional): build playbook to run. Defaults to ''.
            family (str, optional): image family tag name to set for the created image. Defaults to 'k2g-images'.
            logger (Logger, optional): logger object to use. Defaults to None.
        """
        name = name if name != 'GENERATE' else f'build-{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'
        if playbook:
            playbook = f'builds/{playbook}'
        super().__init__(name, image, image_project, disk_size, disk_type, project_id, zone, machine_type,
                         network_tags, playbook, False, logger)
        self.__family = family

    @property
    def __build_dir(self) -> str:
        """The directory where ansible builds are located

        Returns:
            str: The directory where ansible builds are located
        """
        return f'{self.ansible_dir}/playbooks/builds'

    def display_build_options(self) -> bool:
        """Display available build options from the build directory

        Returns:
            bool: True if the build options were displayed successfully, False otherwise
        """
        builds = []
        for content in Path(self.__build_dir).glob('*.yml'):
            builds.append(content.name)
        builds.sort()
        return self.display_info_msg(f'Available builds:\n  {"\n  ".join(builds)}')

    def __run_build_playbook(self, ip: str = None) -> bool:
        """Run the build playbook on the VM

        Args:
            ip (str, optional): ip of the VM. Will get the IP if not provided. Defaults to None.

        Returns:
            bool: True if the playbook was run successfully, False otherwise
        """
        if not ip:
            ip = self.get_instance_public_ip(self.project_id, self._zone, self._name)
        if ip:
            return self.run_ansible_playbook(ip, self._name, self._playbook)
        self.log.error(f'Unable to get IP for {self._name}')
        return False

    def run_build(self) -> bool:
        """Run the build process. Will rerun the build playbook if the VM name already exists and is running incase
        of a failed build and tweaking was performed. Will create a GCP image of the VM boot disk then delete the VM
        when a successful build is performed.

        Returns:
            bool: True if the build was successful, False otherwise
        """
        if self._name in self.get_running_instances(self.project_id, self._zone) and not self.__run_build_playbook():
            self.log.error(f'Failed to build image {self._name}')
            return False
        else:
            if not self.deploy():
                self.log.error(f'Failed to build image {self._name}')
                return False
        if GCPImages(self.project_id).create_clone(self._zone, self._name, self._name, self.__family, True):
            if self.delete_instance(self.project_id, self._zone, self._name):
                self.log.info(f'Successfully built image {self._name}')
                return True
        self.log.error(f'Failed to build image {self._name}')
        return False

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
        name = name if name != 'GENERATE' else f'build-{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'
        if playbook:
            playbook = f'builds/{playbook}'
        super().__init__(name, image, image_project, disk_size, disk_type, project_id, zone, machine_type,
                         network_tags, playbook, False, logger)
        self.__family = family

    @property
    def __build_dir(self):
        return f'{self.ansible_dir}/playbooks/builds'

    def display_build_options(self):
        builds = []
        for content in Path(self.__build_dir).glob('*.yml'):
            builds.append(content.name)
        builds.sort()
        return self.display_info_msg(f'Available builds:\n  {"\n  ".join(builds)}')

    def __run_build_playbook(self, ip: str = None):
        if not ip:
            ip = self.get_instance_public_ip(self.project_id, self._zone, self._name)
        if ip:
            return self.run_ansible_playbook(ip, self._name, self._playbook)
        self.log.error(f'Unable to get IP for {self._name}')
        return False

    def run_build(self):
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

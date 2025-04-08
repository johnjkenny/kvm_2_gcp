from logging import Logger
from time import sleep
from json import dumps

from google.cloud import compute_v1
from google.api_core.operation import Operation
from google.api_core.exceptions import BadRequest

from kvm_2_gcp.utils import Utils


class GCPController(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger=logger)
        self.__client: compute_v1.InstancesClient | None = None
        self.__image_client: compute_v1.ImagesClient | None = None
        self.__zone_op_client: compute_v1.ZoneOperationsClient | None = None
        self.__global_op_client: compute_v1.GlobalOperationsClient | None = None

    @property
    def client(self):
        if self.__client is None:
            try:
                self.__client = compute_v1.InstancesClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP compute client')
        return self.__client

    @property
    def image_client(self):
        if self.__image_client is None:
            try:
                self.__image_client = compute_v1.ImagesClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP image client')
        return self.__image_client

    @property
    def zone_op_client(self):
        if self.__zone_op_client is None:
            try:
                self.__zone_op_client = compute_v1.ZoneOperationsClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP zonal operation client')
        return self.__zone_op_client

    @property
    def global_op_client(self):
        if self.__global_op_client is None:
            try:
                self.__global_op_client = compute_v1.GlobalOperationsClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP global operation client')
        return self.__global_op_client

    def _wait_for_zone_operation(self, operation: Operation, zone: str) -> bool:
        while True:
            result = self.get_zone_operation(self.project_id, zone, operation.name)
            if result:
                if result.status == compute_v1.Operation.Status.DONE:
                    if result.error:
                        self.log.error(f'Operation {operation.name} finished with error: {result.error}')
                        return False
                    self.display_success_msg(f'Operation {operation.name} completed successfully')
                    return True
                self.display_info_msg(f'Waiting for operation {operation.name} to complete...')
            else:
                self.log.error(f'Failed to get operation {operation.name}')
                return False
            sleep(3)

    def _wait_for_global_operation(self, operation: Operation) -> bool:
        while True:
            result = self.get_global_operation(self.project_id, operation.name)
            if result:
                if result.status == compute_v1.Operation.Status.DONE:
                    if result.error:
                        self.log.error(f'Operation {operation.name} finished with error: {result.error}')
                        return False
                    self.display_success_msg(f'Operation {operation.name} completed successfully')
                    return True
                self.display_info_msg(f'Waiting for operation {operation.name} to complete...')
            else:
                self.log.error(f'Failed to get operation {operation.name}')
                return False
            sleep(3)

    def get_instance_public_ip(self, project_id: str, zone: str, name: str) -> str | None:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        instance = self.get_instance(project_id, zone, name)
        if instance:
            for iface in instance.network_interfaces:
                if iface.access_configs:
                    for access in iface.access_configs:
                        access: compute_v1.AccessConfig
                        if access.nat_i_p:
                            return access.nat_i_p
        return None

    def get_instance(self, project_id: str, zone: str, name: str):
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            try:
                return self.client.get(project=project_id, zone=zone, instance=name)
            except BadRequest as error:
                self.log.error(f'Failed to get GCP instance: {error.message}')
            except Exception:
                self.log.exception(f'Failed to get GCP instance {name}')
        return None

    def get_zone_operation(self, project_id: str, zone: str, operation_name: str) -> Operation | None:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.zone_op_client is not None:
            try:
                op: Operation = self.zone_op_client.get(project=project_id, zone=zone, operation=operation_name)
                return op
            except BadRequest as error:
                self.log.error(f'Failed to get GCP operation: {error.message}')
            except Exception:
                self.log.exception(f'Failed to get GCP operation {operation_name}')
        return None

    def get_global_operation(self, project_id: str, operation_name: str) -> Operation | None:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.zone_op_client is not None:
            try:
                op: Operation = self.global_op_client.get(project=project_id, operation=operation_name)
                return op
            except BadRequest as error:
                self.log.error(f'Failed to get GCP global operation: {error.message}')
            except Exception:
                self.log.exception(f'Failed to get GCP global operation {operation_name}')
        return None

    def create_instance(self, project_id: str, zone: str, instance: compute_v1.Instance):
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            try:
                return self.client.insert(project=project_id, zone=zone, instance_resource=instance)
            except BadRequest as error:
                self.log.error(f'Failed to create GCP instance: {error.message}')
                return None
            except Exception:
                self.log.exception('Failed to create GCP instance')
                return None
        return None

    def get_instances(self, project_id: str, zone: str) -> str:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        instances = {'running': [], 'stopped': []}
        if self.client is not None:
            try:
                for instance in self.client.list(project=project_id, zone=zone):
                    status = instance.status
                    if status == 'RUNNING':
                        instances['running'].append(instance.name)
                    elif status in ['TERMINATED', 'STOPPED', 'STOPPING']:
                        instances['stopped'].append(instance.name)
            except BadRequest as error:
                self.log.error(f'Failed to get GCP instances: {error.message}')
            except Exception:
                self.log.exception('Failed to get GCP instances')
        return instances

    def get_running_instances(self, project_id: str, zone: str) -> list:
        return self.get_instances(project_id, zone).get('running', [])

    def get_stopped_instances(self, project_id: str, zone: str) -> list:
        return self.get_instances(project_id, zone).get('stopped', [])

    def delete_instance(self, project_id: str, zone: str, name: str) -> bool:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            try:
                self.log.info(f'Deleting GCP instance {name}')
                operation = self.client.delete(project=project_id, zone=zone, instance=name)
                if operation and self._wait_for_zone_operation(operation, zone):
                    return self._delete_ansible_client_directory(name)
            except BadRequest as error:
                self.log.error(f'Failed to delete GCP instance: {error.message}')
            except Exception:
                self.log.exception(f'Failed to delete GCP instance {name}')
        return False

    def start_instance(self, project_id: str, zone: str, name: str) -> bool:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            self.log.info(f'Starting GCP instance {name}')
            try:
                operation = self.client.start(project=project_id, zone=zone, instance=name)
                if operation:
                    return self._wait_for_zone_operation(operation, zone)
            except BadRequest as error:
                self.log.error(f'Failed to start GCP instance: {error.message}')
            except Exception:
                self.log.exception(f'Failed to start GCP instance {name}')
        return False

    def stop_instance(self, project_id: str, zone: str, name: str) -> bool:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            self.log.info(f'Stopping GCP instance {name}')
            try:
                operation = self.client.stop(project=project_id, zone=zone, instance=name)
                if operation:
                    return self._wait_for_zone_operation(operation, zone)
            except BadRequest as error:
                self.log.error(f'Failed to stop GCP instance: {error.message}')
            except Exception:
                self.log.exception(f'Failed to stop GCP instance {name}')
        return False

    def reboot_instance(self, project_id: str, zone: str, name: str) -> bool:
        if project_id == 'default':
            project_id = self._load_default_project_id()
        if self.client is not None:
            try:
                self.log.info(f'Restarting GCP instance {name}')
                operation = self.client.reset(project=project_id, zone=zone, instance=name)
                if operation:
                    return self._wait_for_zone_operation(operation, zone)
            except BadRequest as error:
                self.log.error(f'Failed to restart GCP instance: {error.message}')
            except Exception:
                self.log.exception(f'Failed to restart GCP instance {name}')
        return False

    def display_instances(self, project_id: str, zone: str):
        return self.display_info_msg(dumps(self.get_instances(project_id, zone), indent=2))

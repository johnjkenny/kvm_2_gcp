from logging import Logger
from time import sleep
from json import dumps

from google.cloud import compute_v1
from google.api_core.operation import Operation
from google.api_core.exceptions import BadRequest

from kvm_2_gcp.utils import Utils


class GCPController(Utils):
    def __init__(self, logger: Logger = None):
        """A module that helps control GCP instances. It provides methods to create, delete, start, stop, and reboot
        instances. Add handling to wait for operations to finish

        Args:
            logger (Logger, optional): logger to use. Defaults to None.
        """
        super().__init__(logger=logger)
        self.__client: compute_v1.InstancesClient | None = None
        self.__image_client: compute_v1.ImagesClient | None = None
        self.__zone_op_client: compute_v1.ZoneOperationsClient | None = None
        self.__global_op_client: compute_v1.GlobalOperationsClient | None = None

    @property
    def client(self) -> compute_v1.InstancesClient | None:
        """Instance client object with credentials set

        Returns:
            compute_v1.InstancesClient | None: GCP instance client
        """
        if self.__client is None:
            try:
                self.__client = compute_v1.InstancesClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP compute client')
        return self.__client

    @property
    def image_client(self) -> compute_v1.ImagesClient | None:
        """Image client object with credentials set

        Returns:
            compute_v1.ImagesClient | None: GCP image client
        """
        if self.__image_client is None:
            try:
                self.__image_client = compute_v1.ImagesClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP image client')
        return self.__image_client

    @property
    def zone_op_client(self) -> compute_v1.ZoneOperationsClient | None:
        """Zone operations client object with credentials set

        Returns:
            compute_v1.ZoneOperationsClient | None: GCP zone operations client
        """
        if self.__zone_op_client is None:
            try:
                self.__zone_op_client = compute_v1.ZoneOperationsClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP zonal operation client')
        return self.__zone_op_client

    @property
    def global_op_client(self) -> compute_v1.GlobalOperationsClient | None:
        """Global operations client object with credentials set

        Returns:
            compute_v1.GlobalOperationsClient | None: GCP global operations client
        """
        if self.__global_op_client is None:
            try:
                self.__global_op_client = compute_v1.GlobalOperationsClient(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to create GCP global operation client')
        return self.__global_op_client

    def _wait_for_zone_operation(self, operation: Operation, zone: str) -> bool:
        """Wait for zone operation to finish and check for errors

        Args:
            operation (Operation): operation to wait for
            zone (str): zone to check for operation

        Returns:
            bool: True if operation finished successfully, False otherwise
        """
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
        """Wait for global operation to finish and check for errors

        Args:
            operation (Operation): operation to wait for

        Returns:
            bool: True if operation finished successfully, False otherwise
        """
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
        """Get the public IP address of a GCP instance

        Args:
            project_id (str): project ID the instance is in
            zone (str): the zone the instance is in
            name (str): the name of the instance

        Returns:
            str | None: the public IP address of the instance, or None if not found
        """
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

    def get_instance(self, project_id: str, zone: str, name: str) -> compute_v1.Instance | None:
        """Get a GCP instance object of name

        Args:
            project_id (str): project ID the instance is in
            zone (str): the zone the instance is in
            name (str): the name of the instance

        Returns:
            compute_v1.Instance | None: the GCP instance object, or None if not found
        """
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
        """Get a GCP zone operation object of name

        Args:
            project_id (str): project ID the operation is in
            zone (str): the zone the operation is in
            operation_name (str): the name of the operation

        Returns:
            Operation | None: the GCP operation object, or None if not found
        """
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
        """Get a GCP global operation object of name

        Args:
            project_id (str): project ID the operation is in
            operation_name (str): the name of the operation

        Returns:
            Operation | None: the GCP operation object, or None if not found
        """
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

    def create_instance(self, project_id: str, zone: str, instance: compute_v1.Instance) -> Operation | None:
        """Create a GCP instance with the provided instance object

        Args:
            project_id (str): project ID to deploy the instance in
            zone (str): the zone to deploy the instance in
            instance (compute_v1.Instance): the instance object to create

        Returns:
            Operation | None: the GCP zone operation object, or None if not found
        """
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

    def get_instances(self, project_id: str, zone: str) -> dict:
        """Get a list of GCP instances in the project and zone

        Args:
            project_id (str): project ID to get instances from
            zone (str): the zone to get instances from

        Returns:
            dict: a dictionary with two lists: 'running' and 'stopped' instances
        """
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
        """Get a list of running GCP instances in the project and zone

        Args:
            project_id (str): project ID to get instances from
            zone (str): the zone to get instances from

        Returns:
            list: a list of running instance names
        """
        return self.get_instances(project_id, zone).get('running', [])

    def get_stopped_instances(self, project_id: str, zone: str) -> list:
        """Get a list of stopped GCP instances in the project and zone

        Args:
            project_id (str): project ID to get instances from
            zone (str): the zone to get instances from

        Returns:
            list: a list of stopped instance names
        """
        return self.get_instances(project_id, zone).get('stopped', [])

    def delete_instance(self, project_id: str, zone: str, name: str) -> bool:
        """Delete a GCP instance with the provided name

        Args:
            project_id (str): project ID to delete the instance from
            zone (str): the zone to delete the instance from
            name (str): the name of the instance to delete

        Returns:
            bool: True if the instance was deleted successfully, False otherwise
        """
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
        """Start a GCP instance with the provided name

        Args:
            project_id (str): project ID to start the instance in
            zone (str): the zone to start the instance in
            name (str): the name of the instance to start

        Returns:
            bool: True if the instance was started successfully, False otherwise
        """
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
        """Stop a GCP instance with the provided name

        Args:
            project_id (str): project ID to stop the instance in
            zone (str): the zone to stop the instance in
            name (str): the name of the instance to stop

        Returns:
            bool: True if the instance was stopped successfully, False otherwise
        """
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
        """Reboot a GCP instance with the provided name

        Args:
            project_id (str): project ID to reboot the instance in
            zone (str): the zone to reboot the instance in
            name (str): the name of the instance to reboot

        Returns:
            bool: True if the instance was rebooted successfully, False otherwise
        """
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

    def display_instances(self, project_id: str, zone: str) -> bool:
        """Display the instances in the project and zone

        Args:
            project_id (str): project ID to get instances from
            zone (str): the zone to get instances from

        Returns:
            bool: True if the instances were displayed successfully, False otherwise
        """
        return self.display_info_msg(dumps(self.get_instances(project_id, zone), indent=2))

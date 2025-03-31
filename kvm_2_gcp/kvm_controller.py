import json
from ipaddress import ip_address, IPv4Address
from logging import Logger
from time import sleep
from pathlib import Path
from uuid import uuid4

from kvm_2_gcp.utils import Utils


class KVMController(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger=logger)

    def __instance_exists(self, vm_name: str, instance: list = None) -> bool:
        """Check if a VM instance exists on the hypervisor. It will return True if the instance exists and False
        otherwise.

        Args:
            vm_name (str): name of the VM to check if it exists
            instance (list, optional): list of instances to check. Defaults to None.

        Returns:
            bool: True if the instance exists, False otherwise
        """
        if instance is None:
            instance = self.get_instances()
        return vm_name in instance['running'] or vm_name in instance['stopped'] or vm_name in instance['paused']

    def __delete_vm_directory(self, vm_name: str) -> bool:
        dir_name = Path(f'{self.vm_dir}/{vm_name}')
        if dir_name.exists():
            self.log.info(f'Deleting VM directory {dir_name}')
            return self._run_cmd(f'rm -rf {dir_name}')[1]
        return True

    def __get_vm_state(self, vm_name: str) -> str:
        """Get the state of a VM using the virsh dominfo command. It will return the state of the VM as a string.

        Args:
            vm_name (str): the name of the VM to get the state of

        Returns:
            str: the state of the VM or an empty string if error
        """
        output = self._run_cmd(f'virsh dominfo {vm_name}')
        if output[1]:
            for line in output[0].splitlines():
                if 'State' in line:
                    return line.split(':')[-1].strip()
        return ''

    def __wait_for_vm_shutdown(self, vm_name: str, max_wait: int = 60, force_shutdown: bool = True) -> bool:
        """Wait for a VM to shutdown by checking the state of the VM every second. If the VM is not shutdown after
        max_wait seconds, it will attempt to force shutdown the VM.

        Args:
            vm_name (str): The name of the VM to wait for shutdown
            max_wait (int, optional): the max grace period for the vm to shutdown. Defaults to 60 (1 min).

        Returns:
            bool: True if successful, False otherwise
        """
        count = 0
        while count < max_wait:
            print(f'\rWaiting for VM {vm_name} to shutdown. {count}/{max_wait} seconds', end='')
            if self.is_vm_stopped(vm_name):
                print('')  # flush to new line on console
                return True
            count += 1
            sleep(1)
        if force_shutdown:
            self.log.info(f'VM {vm_name} failed to shutdown after {max_wait} seconds. Force shutting down...')
            return self.force_shutdown_vm(vm_name)
        self.log.error(f'Failed to shutdown VM {vm_name} after {max_wait} seconds')
        return False

    def __undefine_vm(self, vm_name: str) -> bool:
        """Undefine a VM using the virsh undefine command. This will remove the VM configuration from the hypervisor.
        This method should be used when deleting a VM to remove all traces of the VM from the hypervisor.

        Args:
            vm_name (str): the name of the VM to undefine

        Returns:
            bool: True if successful, False otherwise
        """
        if self._run_cmd(f'virsh undefine {vm_name}')[1]:
            return True
        self.log.error(f'Failed to undefine VM {vm_name}')
        return False

    def __split_size_suffix(self, size: str):
        digit = []
        suffix = []
        for char in size:
            if char.isdigit():
                digit.append(char)
            elif char.isalpha():
                suffix.append(char)
        return int(''.join(digit)), ''.join(suffix).lower()

    def __convert_size_to_bytes(self, size: int | str):
        if isinstance(size, int):
            return size
        if isinstance(size, str):
            if size.isdigit():
                return int(size)
            digit, suffix = self.__split_size_suffix(size)
            if suffix in ['t', 'tb', 'tib']:
                return digit * 1024 ** 4
            if suffix in ['g', 'gb', 'gib']:
                return digit * 1024 ** 3
            if suffix in ['m', 'mb', 'mib']:
                return digit * 1024 ** 2
            if suffix in ['k', 'kb', 'kib']:
                return digit * 1024
            self.log.error(f'Invalid size suffix: {suffix}')
        else:
            self.log.error(f'Invalid size type: {size}, {type(size)}')
        return 0

    def __create_data_disk(self, vm_name: str, size: int | str, name: str = 'GENERATE'):
        self.log.info(f'Creating data disk for VM {vm_name}')
        size = self.__convert_size_to_bytes(size)
        if not size:
            return False
        vm_dir = f'{self.vm_dir}/{vm_name}'
        name = name if name != 'GENERATE' else 'data-' + uuid4().hex[:8]
        disk_name = f'{vm_dir}/{name}.qcow2'
        if self._run_cmd(f'qemu-img create -f qcow2 {disk_name} {size}')[1]:
            return disk_name
        self.log.error('Failed to create data disk')
        return ''

    def __find_next_vm_target_disk(self, vm_name: str):
        disks = self.get_instance_disks(vm_name)
        if disks:
            targets = list(disks.keys())
            targets.sort()
            last_target = targets[-1].lower()
            if last_target[-1] == 'z':
                self.log.error('No more targets available')
                return ''
            return last_target[:-1] + chr(ord(last_target[-1]) + 1)
        return 'sda'

    def __attach_data_disk(self, vm_name: str, disk_name: str) -> bool:
        self.log.info(f'Attaching data disk {disk_name} to VM {vm_name}')
        serial = disk_name.split('/')[-1].split('.')[0]
        target = self.__find_next_vm_target_disk(vm_name)
        if not target:
            self.log.error('Failed to find target for data disk')
            return False
        live = ' --live' if self.is_vm_running(vm_name) else ''
        cmd = f'virsh attach-disk {vm_name} {disk_name} --driver qemu --subdriver qcow2 --cache none --serial {serial}'
        cmd += f' --target {target} --targetbus scsi{live} --persistent'
        if self._run_cmd(cmd)[1]:
            return True
        self.log.error('Failed to attach data disk to vm')
        return False

    def __remove_instance_cdrom(self, vm_name: str, target: str) -> bool:
        live = ' --live' if self.is_vm_running(vm_name) else ''
        if self._run_cmd(f'virsh detach-disk {vm_name} {target}{live} --config')[1]:
            self.log.info(f'Removed {target} from {vm_name}')
            return True
        self.log.error(f'Failed to remove {target} from {vm_name}')
        return False

    def _wait_for_vm_init(self, vm_name: str, max_wait: int = 120) -> str:
        """Wait for a VM to initialize by checking the state of the VM every 5 seconds. If the VM is not initialized
        after max_wait seconds, it will return False. When the VM is initialized, it will display the IP address
        for interface 1 of the VM and return True.

        Args:
            vm_name (str): the name of the VM to wait for initialization
            max_wait (int, optional): the max wait time for VM initialization. Defaults to 120 (2 mins).

        Returns:
            str: IP address of the VM or empty string if not found
        """
        count = 0
        while count < max_wait:
            print(f'\rWaiting for VM {vm_name} to initialize. {count}/{max_wait} seconds', end='')
            ip = self.__display_vm_is_up(vm_name)
            if ip:
                return ip
            count += 5
            sleep(5)
        self.log.error(f'Failed to wait for vm {vm_name} to initialize after {max_wait} seconds')
        return ''

    def list_vms(self) -> bool:
        """List all VMs on the hypervisor. It will list all VMs in a table format with the VM name and state"""
        return self.display_info_msg(f'VMs:\n{json.dumps(self.get_instances(True), indent=2)}')

    def delete_vm(self, vm_name: str) -> bool:
        """Delete a VM by shutting it down, undefine it, and deleting its directory. This will remove all traces of
        the VM from the hypervisor and the VM directory.

        Args:
            vm_name (str): The name of the VM to delete

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Deleting VM {vm_name}')
        instance = self.get_instances()
        if self.__instance_exists(vm_name, instance):
            if vm_name in instance.get('running', []):
                if not self.shutdown_vm(vm_name):
                    return False
            if not self.__undefine_vm(vm_name):
                return False
        return self.__delete_vm_directory(vm_name)

    def shutdown_vm(self, vm_name: str) -> bool:
        """Shutdown a VM using the virsh shutdown command. This will attempt to gracefully shutdown the VM. If the
        VM is not running, it will exit True. It will also wait for the VM to shutdown before returning. If
        the VM failed to shutdown in the max_wait time, it will attempt to force shutdown the VM.

        Args:
            vm_name (str): the name of the VM to shutdown

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Shutting down VM {vm_name}')
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return False
        if vm_name not in instances.get('running', []):
            self.log.info(f'VM {vm_name} is not running')
            return True
        if self._run_cmd(f'virsh shutdown {vm_name}')[1]:
            return self.__wait_for_vm_shutdown(vm_name)
        self.log.error(f'Failed to shutdown VM {vm_name}')
        return False

    def force_shutdown_vm(self, vm_name: str) -> bool:
        """Force shutdown a VM by using the virsh destroy command. This is not a graceful shutdown and can cause data
        loss.

        Args:
            vm_name (str): the name of the VM to force shutdown

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Force shutting down VM {vm_name}')
        if self._run_cmd(f'virsh destroy {vm_name}')[1]:
            return self.__wait_for_vm_shutdown(vm_name, 10, False)
        self.log.error(f'Failed to force shutdown VM {vm_name}')
        return False

    def start_vm(self, vm_name: str) -> str:
        """Start a VM using the virsh start command. If the VM is already running, it will not be started again and
        will exit True.

        Args:
            vm_name (str): the name of the VM to start

        Returns:
            str: IP address of the VM or empty string if not found
        """
        self.log.info(f'Starting VM {vm_name}')
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return ''
        if vm_name in instances.get('running', []):
            self.log.info(f'VM {vm_name} is already running')
            return True
        if self._run_cmd(f'virsh start {vm_name}')[1]:
            return self._wait_for_vm_init(vm_name)
        self.log.error(f'Failed to start VM {vm_name}')
        return ''

    def soft_reset_vm(self, vm_name: str) -> bool:
        """Soft reset a VM by shutting it down gracefully and starting it back up. If the VM is not running,
        it will be started.

        Args:
            vm_name (str): the name of the VM to soft reset

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Soft resetting VM {vm_name}')
        if self.shutdown_vm(vm_name):
            return self.start_vm(vm_name)
        self.log.error(f'Failed to soft reset VM {vm_name}')
        return False

    def hard_reset_vm(self, vm_name: str) -> bool:
        """Hard reset a VM by using the virsh reset command. This is not a graceful shutdown and can cause data loss.
        If the VM is not running, it will be started.

        Args:
            vm_name (str): the vm name to hard reset

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Hard resetting VM {vm_name}')
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return False
        if vm_name not in instances.get('running', []):
            self.log.info(f'VM {vm_name} is not running. Starting...')
            return self.start_vm(vm_name)
        if self._run_cmd(f'virsh reset {vm_name}')[1]:
            return self._wait_for_vm_init(vm_name)
        self.log.error(f'Failed to hard reset VM {vm_name}')
        return False

    def reboot_vm(self, vm_name: str) -> bool:
        """Reboot a VM by using the virsh reboot command. If the VM is not running, it will be started.

        Args:
            vm_name (str): the name of the VM to reboot

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Rebooting VM {vm_name}')
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return False
        if vm_name not in instances.get('running', []):
            self.log.info(f'VM {vm_name} is not running. Starting...')
            return self.start_vm(vm_name)
        if self._run_cmd(f'virsh reboot {vm_name}')[1]:
            return self._wait_for_vm_init(vm_name)
        self.log.error(f'Failed to reboot VM {vm_name}')
        return False

    def purge_vms(self, force: bool = False) -> bool:
        """Purge VM images and delete all images for non running VMs. This will also delete cloud image templates. This
        method is very close to the initialize method, but keeps intact the cache file and any running VMs.

        Args:
            force (bool, optional): Force the purge without user input. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if force or input('Purge VMs and delete all instances for non running VMs? [y/n]: ').lower() == 'y':
            running_instances = self.__get_running_instances()
            for vm in Path(self.vm_dir).iterdir():
                if vm.name in running_instances:
                    continue
                if not self.delete_vm(vm.name):
                    self.log.error(f'Failed to delete VM {vm.name}')
                    return False
            return True
        return False

    def get_instances(self, sort: bool = False) -> dict:
        instances = {'running': [], 'stopped': [], 'paused': []}
        rsp = self._run_cmd('virsh list --all')
        if rsp[1]:
            for line in rsp[0].splitlines():
                if 'running' in line:
                    instances['running'].append(line.split()[1])
                elif 'shut off' in line:
                    instances['stopped'].append(line.split()[1])
                elif 'paused' in line:
                    instances['paused'].append(line.split()[1])
        if sort:
            instances['running'].sort()
            instances['stopped'].sort()
            instances['paused'].sort()
        return instances

    def is_vm_running(self, vm_name: str) -> bool:
        return self.__get_vm_state(vm_name) == 'running'

    def is_vm_stopped(self, vm_name: str) -> bool:
        return self.__get_vm_state(vm_name) == 'shut off'

    def is_vm_paused(self, vm_name: str) -> bool:
        return self.__get_vm_state(vm_name) == 'paused'

    def get_running_instances(self) -> list:
        """Get all running instances on the hypervisor.

        Returns:
            list: list of running VM names
        """
        return self.get_instances().get('running', [])

    def get_stopped_instances(self) -> list:
        """Get all stopped instances on the hypervisor.

        Returns:
            list: list of stopped VM names
        """
        return self.get_instances().get('stopped', [])

    def get_paused_instances(self) -> list:
        """Get all paused instances on the hypervisor.

        Returns:
            list: list of paused VM names
        """
        return self.get_instances().get('paused', [])

    def get_instance_disks(self, vm_name: str) -> dict:
        """Get the disks attached to a VM using the virsh domblklist command. It will return a dictionary of disks with
        the target as the key and the source as the value

        Args:
            vm_name (str): name of the vm to get the disks for

        Returns:
            dict: dictionary of disks with the target as the key and the source as the value
        """
        disks = {}
        rsp = self._run_cmd(f'virsh domblklist {vm_name}')
        if rsp[1]:
            for line in rsp[0].splitlines():
                if '/' in line:
                    info = line.split()
                    disks[info[0]] = info[1]
        return disks

    def eject_instance_iso(self, vm_name: str, remove_cdrom: bool = True) -> bool:
        disks: dict = self.get_instance_disks(vm_name)
        for target, source in disks.items():
            if source.endswith('.iso'):
                if self._run_cmd(f'virsh change-media {vm_name} {target} --eject --config')[1]:
                    self.log.info(f'Ejected {source} from {vm_name}')
                    if remove_cdrom:
                        return self.__remove_instance_cdrom(vm_name, target)
                    return True
        self.log.error(f'Failed to remove attached iso from {vm_name}')
        return False

    def detach_data_disk(self, vm_name: str, disk_name: str):
        # ToDo: Create method to detach live disk from vm
        pass

    def create_data_disk(self, vm_name: str, size: bytes | str, name: str = 'GENERATE') -> bool:
        disk_name = self.__create_data_disk(vm_name, size, name)
        if disk_name:
            return self.__attach_data_disk(vm_name, disk_name)
        return False

    def get_vm_interfaces(self, vm_name: str):
        interfaces = {}
        rsp = self._run_cmd(f'virsh guestinfo {vm_name}', True)
        if rsp[1]:
            for line in rsp[0].splitlines():
                if line.startswith('if.'):
                    if line.startswith('if.count'):
                        continue
                    key, _, value = line.split()
                    num = key.split('.')[1]
                    if num not in interfaces:
                        interfaces[num] = {}
                    if 'name' in key:
                        interfaces[num]['name'] = value
                    elif 'hwaddr' in key:
                        interfaces[num]['hwaddr'] = value
                    elif '0.addr' in key:
                        interfaces[num]['address'] = value
                    elif '0.prefix' in key:
                        interfaces[num]['prefix'] = value
        return interfaces

    def get_eth_interfaces(self, vm_name: str):
        eth = {}
        interfaces = self.get_vm_interfaces(vm_name)
        for num, interface in interfaces.items():
            if interface.get('name', '').startswith('eth'):
                eth[num] = interface
        return eth

    def display_vm_interfaces(self, vm_name: str):
        return self.display_info_msg(json.dumps(self.get_eth_interfaces(vm_name), indent=2))

    def get_vm_ip_by_interface_name(self, vm_name: str, interface_name: str = 'eth0'):
        """Get the IP address of a VM using the virsh guestinfo command. This will return the IP address of the VM
        for the specified interface name. If the IP address is not found, it will return None. An ignore_error option
        is available to help in determining if a VM has been initialized when deploying a new VM. The IP address
        will not be set until the VM has POSTed to a certain point.

        Args:
            vm_name (str): name of the vm get the interface IP address
            interface_name (str, optional): interface name to get IP address. Defaults to 'if.1.addr.0.addr'.

        Returns:
            str or None: IP address of the VM or None if not found
        """
        interfaces = self.get_eth_interfaces(vm_name)
        for interface in interfaces.values():
            if interface.get('name') == interface_name:
                return interface.get('address')
        return ''

    def __display_vm_is_up(self, vm_name: str, ignore_error: bool = False) -> str:
        """Display the IP address of a VM using the virsh guestinfo command. This will display the IP address of the VM
        to console.

        Args:
            vm_name (str): name of the VM to display the IP address
            ignore_error (bool, optional): option to ignore any error. Defaults to False.

        Returns:
            str: IP address of the VM or empty string if not found
        """
        ip = self.get_vm_ip_by_interface_name(vm_name)
        if ip:
            try:
                ip_obj = ip_address(ip)
                if isinstance(ip_obj, IPv4Address):
                    self.display_success_msg(f'\nVM {vm_name} is up. IP: {ip}')
                    return ip
            except Exception:
                if ignore_error:
                    return False
                self.log.error(f'Invalid IP address for {vm_name}: {ip}')
        return ''

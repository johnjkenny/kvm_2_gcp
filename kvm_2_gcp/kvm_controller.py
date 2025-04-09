import json
from ipaddress import ip_address, IPv4Address
from logging import Logger
from time import sleep
from pathlib import Path
from uuid import uuid4
from os import remove
from xml.etree import ElementTree

from kvm_2_gcp.utils import Utils


class KVMController(Utils):
    def __init__(self, logger: Logger = None):
        """KVM controller to control KVM hypervisor

        Args:
            logger (Logger, optional): log object to use. Defaults to None.
        """
        super().__init__(logger=logger)

    @property
    def __new_network_data(self) -> str:
        """string xml data to add a new network interface to a VM. Hardcoded to use bridge virbr0.

        Returns:
            str: xml data to add a new network interface
        """
        return '''<interface type='bridge'>
  <source bridge='virbr0'/>
  <model type='virtio'/>
</interface>'''

    def __remove_network_data(self, mac: str) -> str:
        """string xml data to remove a network interface from a VM using the mac address

        Args:
            mac (str): MAC address of the network interface to remove

        Returns:
            str: xml data to remove a network interface
        """
        return f'''<interface type="bridge">
  <mac address="{mac}"/>
  <source bridge='virbr0'/>
  <model type="virtio"/>
</interface>'''

    def __remove_disk_data(self, disk_location: str, target: str) -> str:
        """string xml data to remove a disk from a VM using the disk location and target

        Args:
            disk_location (str): location of the disk to remove (path to the disk file)
            target (str): target of the disk to remove (ex: sda, sdb)

        Returns:
            str: xml data to remove a disk
        """
        return f'''<disk type='file' device='disk'>
  <source file='{disk_location}'/>
  <target dev='{target}' bus='scsi'/>
</disk>'''

    def __instance_exists(self, vm_name: str, vms: list = None) -> bool:
        """Check if a VM exists on the hypervisor.

        Args:
            vm_name (str): name of the VM to check if it exists
            vms (list, optional): list of vms to check. Defaults to None.

        Returns:
            bool: True if the vm exists, False otherwise
        """
        if vms is None:
            vms = self.get_instances()
        return vm_name in vms['running'] or vm_name in vms['stopped'] or vm_name in vms['paused']

    def __delete_vm_directory(self, vm_name: str) -> bool:
        """Delete the VM directory and all its contents. Will also delete the ansible client directory

        Args:
            vm_name (str): name of the VM to delete

        Returns:
            bool: True if successful, False otherwise
        """
        dir_name = Path(f'{self.vm_dir}/{vm_name}')
        if dir_name.exists():
            self.log.info(f'Deleting VM directory {dir_name}')
            return self._run_cmd(f'rm -rf {dir_name}')[1] and self._delete_ansible_client_directory(vm_name)
        return True

    def __get_vm_state(self, vm_name: str) -> str:
        """Get the state of a VM using the virsh dominfo command.

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
        print('')  # flush to new line on console
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

    def __split_size_suffix(self, size: str) -> tuple[float, str]:
        """Split the provided size string into a tuple of the numeric part and the suffix part. The numeric part will be
        converted to a float and the suffix part will be converted to lowercase. The suffix part will be empty if no
        suffix is found. The numeric part will be 0.0 if no numeric part is found.

        Args:
            size (str): size string to split

        Returns:
            tuple[float, str]: tuple of the numeric part and the suffix part
        """
        digit = []
        suffix = []
        decimal_found = False
        for char in size:
            if char.isdigit() or (char == '.' and not decimal_found):
                if char == '.':
                    decimal_found = True
                digit.append(char)
            elif char.isalpha():
                suffix.append(char)
        try:
            return float(''.join(digit)), ''.join(suffix).lower()
        except ValueError:
            self.log.error(f'Unable to parse numeric part from size: {size}')
            return 0.0, ''

    def __convert_size_to_bytes(self, size: int | str) -> int:
        """Convert the provided size to bytes. If the size is a string, it can be a number with a suffix (k, m, g, t)
        or a number without a suffix. The suffix can be in lowercase or uppercase.

        Args:
            size (int | str): size to convert to bytes

        Returns:
            int: size in bytes or 0 if invalid
        """
        if isinstance(size, int):
            return size
        if isinstance(size, str):
            if size.isdigit():
                return int(size)
            digit, suffix = self.__split_size_suffix(size)
            if suffix in ['t', 'tb', 'tib']:
                return int(digit * 1024 ** 4)
            if suffix in ['g', 'gb', 'gib']:
                return int(digit * 1024 ** 3)
            if suffix in ['m', 'mb', 'mib']:
                return int(digit * 1024 ** 2)
            if suffix in ['k', 'kb', 'kib']:
                return int(digit * 1024)
            self.log.error(f'Invalid size suffix: {suffix}')
        else:
            self.log.error(f'Invalid size type: {size}, {type(size)}')
        return 0

    def __create_data_disk(self, vm_name: str, size: int | str, name: str = 'GENERATE') -> str:
        """Create a data disk for a VM using the qemu-img command. The disk will be created in the VM directory
        with .qcow2 suffix. Will generate a name for the disk if specified to do so. The size will be converted to bytes

        Args:
            vm_name (str): name of the VM to create the disk for
            size (int | str): size of the disk to create. Can be a number or a string with a suffix (k, m, g, t)
            name (str, optional): name to give to the disk. Defaults to 'GENERATE'.

        Returns:
            str: disk name if successful, empty string otherwise
        """
        size = self.__convert_size_to_bytes(size)
        if not size:
            return False
        name = name if name != 'GENERATE' else 'data-' + uuid4().hex[:8]
        disk_name = f'{self.vm_dir}/{vm_name}/{name}.qcow2'
        if self._run_cmd(f'qemu-img create -f qcow2 {disk_name} {size}')[1]:
            self.log.info(f'Successfully created data disk {disk_name} for {vm_name}')
            return disk_name
        self.log.error(f'Failed to create data disk {disk_name} for {vm_name}')
        return ''

    def __find_next_vm_target_disk(self, vm_name: str) -> str:
        """Find the next available target disk for a VM. The target disk will be in the format of sda, sdb, sdc, etc.

        Args:
            vm_name (str): name of the VM to find the target disk for

        Returns:
            str: next available target disk or empty string if not found
        """
        disks = self.get_vm_disks(vm_name)
        if disks:
            targets = list(disks.keys())
            targets.sort()
            last_target = targets[-1].lower()
            if last_target[-1] == 'z':
                self.log.error('No more targets available')
                return ''
            return last_target[:-1] + chr(ord(last_target[-1]) + 1)
        return 'sda'

    def __attach_data_disk(self, vm_name: str, disk_name: str, vms: dict) -> bool:
        """Attach a data disk to a VM using the virsh attach-disk command.

        Args:
            vm_name (str): name of the VM to attach the disk to
            disk_name (str): name of the disk to attach
            vms (dict): dictionary of VMs to check if the VM is running or not

        Returns:
            bool: True if successful, False otherwise
        """
        serial = f'{vm_name}-{disk_name.split("/")[-1].split(".")[0]}'
        target = self.__find_next_vm_target_disk(vm_name)
        if not target:
            self.log.error(f'Failed to find target for data disk {disk_name} on {vm_name}')
            return False
        live = ' --live' if vm_name in vms.get('running', []) else ''
        cmd = f'virsh attach-disk {vm_name} {disk_name} --driver qemu --subdriver qcow2 --cache none --serial {serial}'
        cmd += f' --target {target} --targetbus scsi{live} --persistent'
        if self._run_cmd(cmd)[1]:
            self.log.info(f'Successfully attached data disk {disk_name} to {vm_name}')
            return True
        self.log.error(f'Failed to attach data disk {disk_name} to {vm_name}')
        return False

    def __remove_instance_cdrom(self, vm_name: str, target: str) -> bool:
        """Remove a CDROM device from a VM using the virsh detach-disk command.

        Args:
            vm_name (str): name of the VM to remove the CDROM from
            target (str): target of the CDROM to remove (ex: sda, sdb)

        Returns:
            bool: True if successful, False otherwise
        """
        live = ' --live' if self.is_vm_running(vm_name) else ''
        if self._run_cmd(f'virsh detach-disk {vm_name} {target}{live} --config')[1]:
            self.log.info(f'Removed {target} from {vm_name}')
            return True
        self.log.error(f'Failed to remove {target} from {vm_name}')
        return False

    def __bytes_to_human_readable(self, unit: int | float, unit_index: int = 0, base: int = 1024) -> str:
        """Convert unit to human readable format. Default options convert bytes to binary units. Unit 2048 will be
        converted to 2 KiB. Use a higher unit_index to convert larger units to smaller units. For example,
        unit_index = 1 will convert 2048 unit to 2 MiB (2048 KiB = 2 MiB).

        Args:
            num_bytes (int | float): bytes to convert
            unit_index (int, optional): The starting index for the conversion. Defaults to 0.
                0 = B, 1 = KiB, 2 = MiB, 3 = GiB, 4 = TiB, 5 = PiB
            base (int, optional): the base to use for conversion. Defaults to 1024 (binary, ex: GiB).

        Returns:
            str: human readable unit conversion to 3 decimal places or original bytes on failure
        """
        suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
        try:
            num = float(unit)
            while num >= base and unit_index < len(suffixes) - 1:
                num /= 1024.0
                unit_index += 1
            suffix = suffixes[unit_index] if base == 1024 else suffixes[unit_index].replace('i', '')
            if num.is_integer():
                return f"{int(num)} {suffix}"
            return f"{num:.3f} {suffix}"
        except Exception:
            self.log.exception('Failed to convert bytes to human readable format')
        return f'{unit}'

    def __get_shutdown_vm_interfaces(self, vm_name: str) -> dict:
        """Get the interfaces attached to a VM using the virsh dumpxml command. It will return a dictionary of
        found interfaces with their mac, source, and model.

        Args:
            vm_name (str): name of the vm to get the interfaces for

        Returns:
            dict: vm interfaces dict
        """
        interfaces = {}
        rsp = self._run_cmd(f'virsh dumpxml {vm_name}')
        if rsp[1]:
            root = ElementTree.fromstring(rsp[0])
            cnt = 1
            for iface in root.findall(".//devices/interface"):
                interfaces[cnt] = {}
                mac_elem = iface.find('mac')
                source = iface.find('source')
                model = iface.find('model')
                if mac_elem is not None:
                    interfaces[cnt]['mac'] = mac_elem.get('address')
                if source is not None:
                    interfaces[cnt]['source'] = source.get('bridge')
                if model is not None:
                    interfaces[cnt]['model'] = model.get('type')
                cnt += 1
        return interfaces

    def __display_vm_is_up(self, vm_name: str, ignore_error: bool = False) -> str:
        """Display the IP address of a VM using the virsh guestinfo command. This will display the IP address of the VM
        to console.

        Args:
            vm_name (str): name of the VM to display the IP address
            ignore_error (bool, optional): option to ignore any error. Defaults to False.

        Returns:
            str: IP address of the VM or empty string if not found
        """
        ip = self.get_vm_ip_by_index(vm_name)
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

    def __create_add_network_file(self, vm_name: str) -> str:
        """Create xml file that will create a new network interface for a VM. The file is located in the VM directory
        and will be auto-deleted when the interface is created or overridden when attempted to be created again.

        Args:
            vm_name (str): name of the vm to create the network interface for

        Returns:
            str: xml file path
        """
        config_file = f'{self.vm_dir}/{vm_name}/add-network.xml'
        try:
            with open(config_file, 'w') as file:
                file.write(self.__new_network_data + '\n')
            return config_file
        except Exception:
            self.log.exception(f'Failed to create network interface file {config_file}')
        return ''

    def __create_remove_network_file(self, vm_name: str, mac: str) -> str:
        """Create xml file that will remove a network interface for a VM. The file is located in the VM directory

        Args:
            vm_name (str): name of the vm to remove the network interface for
            mac (str): mac address of the network interface to remove

        Returns:
            str: xml file path
        """
        config_file = f'{self.vm_dir}/{vm_name}/remove-network.xml'
        try:
            with open(config_file, 'w') as file:
                file.write(self.__remove_network_data(mac) + '\n')
            return config_file
        except Exception:
            self.log.exception(f'Failed to create network remove file {config_file}')
        return ''

    def __create_remove_disk_file(self, vm_name: str, disk_location: str, target: str) -> str:
        """Create xml file that will remove a disk from a VM. The file is located in the VM directory and will be
        auto-deleted when the disk is removed or overridden when attempted to be removed again.

        Args:
            vm_name (str): name of the vm to remove the disk from
            disk_location (str): location of the disk to remove
            target (str): target of the disk to remove (ex: sda, sdb)

        Returns:
            str: xml file path
        """
        config_file = f'{self.vm_dir}/{vm_name}/remove-disk.xml'
        try:
            with open(config_file, 'w') as file:
                file.write(self.__remove_disk_data(disk_location, target) + '\n')
            return config_file
        except Exception:
            self.log.exception(f'Failed to create disk remove file {config_file}')
        return ''

    def __remove_config_file(self, config_file: str) -> bool:
        """Delete the config file after use.

        Args:
            config_file (str): path to the config file to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            remove(config_file)
            return True
        except Exception:
            self.log.exception(f'Failed to remove file {config_file}')
        return False

    def __attach_device(self, vm_name: str, config_file: str, instances: dict = None) -> bool:
        """Attach a device to a VM using the virsh attach-device command. This will use the xml config file to
        attach certain devices to the VM. The config file is located in the VM directory

        Args:
            vm_name (str): name of the VM to attach the device to
            config_file (str): the path to the xml config file to attach
            instances (dict, optional): hypervisor instances. Defaults to None.

        Returns:
            bool: True if successful, False otherwise
        """
        if not instances:
            instances = self.get_instances()
        live = ' --live --persistent' if vm_name in instances.get('running', []) else ''
        return self._run_cmd(f'virsh attach-device {vm_name} {config_file} --config{live}')[1]

    def __detach_device(self, vm_name: str, config_file: str, instances: dict = None) -> bool:
        """Detach a device from a VM using the virsh detach-device command. This will use the xml config file to
        remove certain devices from the VM. The config file is located in the VM directory

        Args:
            vm_name (str): vm name to detach the device from
            config_file (str): path to the xml config file to detach
            instances (dict, optional): hypervisor instances. Defaults to None.

        Returns:
            bool: True if successful, False otherwise
        """
        if not instances:
            instances = self.get_instances()
        live = ' --live --persistent' if vm_name in instances.get('running', []) else ''
        return self._run_cmd(f'virsh detach-device {vm_name} {config_file} --config{live}')[1]

    def __unmount_system_disk(self, vm_name: str, device: str, disks: dict) -> bool:
        """Unmount a system disk from a VM using the ansible playbook. This will run the unmount_disk.yml playbook

        Args:
            vm_name (str): vm name to unmount the disk from
            device (str): disk device to unmount
            disks (dict): dictionary of disks with the target as the key and the source as the value

        Returns:
            bool: True if successful, False otherwise
        """
        ip = self.get_vm_ip_by_index(vm_name)
        if ip:
            device_name = f'{vm_name}-{disks[device]["location"].split("/")[-1].split(".")[0]}-part1'
            if self.run_ansible_playbook(ip, vm_name, 'unmount_disk.yml', {'device_name': device_name}):
                self.log.info(f'Successfully unmounted {device} on {vm_name}')
                return True
            self.log.error(f'Failed to unmount {device} on {vm_name}')
        else:
            self.log.error(f'Failed to get IP address to unmount {device} on {vm_name}')
        return False

    def __mount_system_disk(self, vm_name: str, device_name: str, mount: str) -> bool:
        """Mount a system disk to a VM using the ansible playbook. This will run the mount_disk.yml playbook

        Args:
            vm_name (str): name of the VM to mount the disk to
            device_name (str): disk device to mount (ex: sda, sdb)
            mount (str): location to mount the disk (ex: /mnt/disk-name)

        Returns:
            bool: True if successful, False otherwise
        """
        ip = self.get_vm_ip_by_index(vm_name)
        if ip:
            if self.run_ansible_playbook(ip, vm_name, 'mount_disk.yml', {'device_name': device_name, 'mount': mount}):
                self.log.info(f'Successfully mounted {device_name} on {vm_name}')
                return True
            self.log.error(f'Failed to mount {device_name} on {vm_name}')
        else:
            self.log.error(f'Failed to get IP address to mount {device_name} on {vm_name}')
        return False

    def __remove_data_disk(self, vm_name: str, device: str, disks: dict, vms: dict) -> bool:
        """Remove a data disk from a VM using the virsh detach-device command. It creates an xml config file to remove
        the device then, removes the disk then deletes the config file.

        Args:
            vm_name (str): name of the VM to remove the disk from
            device (str): disk device to remove (ex: sda, sdb)
            disks (dict): dictionary of disks with the target as the key and the source as the value
            vms (dict): dictionary of VMs with the state as the key and a list of VM names as the value

        Returns:
            bool: True if successful, False otherwise
        """
        config_file = self.__create_remove_disk_file(vm_name, disks[device]['location'], device)
        if config_file and self.__detach_device(vm_name, config_file, vms):
            if self.__remove_config_file(config_file):
                self.log.info(f'Successfully removed disk {device} from {vm_name}')
                return True
        self.log.error(f'Failed to remove disk {device} from {vm_name}')
        return False

    def __delete_vm_disk(self, disk_name: str) -> bool:
        """Delete a VM disk.

        Args:
            disk_name (str): name of the disk to delete (full path)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            remove(disk_name)
            self.log.info(f'Deleted disk {disk_name}')
            return True
        except Exception:
            self.log.exception(f'Failed to delete disk {disk_name}')
            return False

    def __validate_disk_change(self, vm_name: str, force: bool = False) -> bool:
        """Validate if the VM is running and if so, shutdown the VM before resizing the disk. If force is True, it will
        automatically shutdown the VM without prompting the user.

        Args:
            vm_name (str): vm name to validate
            force (bool, optional): option to skip shutdown prompt. Defaults to False.

        Returns:
            bool: True if the VM is not running or shutdown successfully, False otherwise
        """
        vms = self.get_instances()
        if vm_name in vms.get('running', []):
            if force or input(f'VM {vm_name} is running. Shutdown? [y/n]: ').lower() == 'y':
                if not self.shutdown_vm(vm_name):
                    return False
            else:
                self.log.error(f'VM {vm_name} is running. Cannot increase disk size')
                return False
        return True

    def __increase_disk_size(self, vm_name: str, device: str, size: int | str, force: bool = False) -> bool:
        """Increase the size of a VM disk using the qemu-img resize command. This will increase the size of the disk
        by the specified size. VM needs to be powered off so if powered on will be prompted to shutdown unless force
        is True

        Args:
            vm_name (str): name of the vm to increase the disk size
            device (str): name of the disk to increase the size (full path to disk)
            size (int | str): new size of the disk in bytes or human readable format (ex: 10G)
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if self.__validate_disk_change(vm_name, force):
            size_bytes = self.__convert_size_to_bytes(size)
            if size_bytes and self._run_cmd(f'qemu-img resize {device} +{size_bytes}')[1]:
                self.log.info(f'Successfully increased disk {device} by {size}')
                return True
            self.log.error(f'Failed to increase disk {device}')
        return False

    def __set_vm_memory(self, vm_name: str, memory: int) -> bool:
        """Sets the VMs memory by setting the setmaxmem and setmem virsh commands, setting the allowed max memory
        and the current memory

        Args:
            vm_name (str): name of the vm to set the memory for
            memory (int): new memory size in MB

        Returns:
            bool: True if successful, False otherwise
        """
        if not memory:
            return True
        memory_kb = memory * 1024
        if not self._run_cmd(f'virsh setmaxmem {vm_name} {memory_kb} --config')[1]:
            self.log.error(f'Failed to set max memory for {vm_name} to {memory_kb} KiB')
            return False
        self.log.info(f'Successfully set max memory for {vm_name} to {memory_kb} KiB')
        if not self._run_cmd(f'virsh setmem {vm_name} {memory_kb} --config')[1]:
            self.log.error(f'Failed to set current memory for {vm_name} to {memory_kb} KiB')
            return False
        self.log.info(f'Successfully set current memory for {vm_name} to {memory_kb} KiB')
        return True

    def __set_vm_cpu(self, vm_name: str, cpu: int) -> bool:
        """Sets the CPU count for a VM using the virsh setvcpus command. This will set the max CPU count and the
        current CPU count for the VM.

        Args:
            vm_name (str): name of the vm to set the CPU count for
            cpu (int): number of CPUs to set for the VM

        Returns:
            bool: True if successful, False otherwise
        """
        if not cpu:
            return True
        if not self._run_cmd(f'virsh setvcpus {vm_name} {cpu} --maximum --config')[1]:
            self.log.error(f'Failed to set max CPU count for {vm_name}')
            return False
        self.log.info(f'Successfully set max CPU count for {vm_name} to {cpu}')
        if not self._run_cmd(f'virsh setvcpus {vm_name} {cpu} --config')[1]:
            self.log.error(f'Failed to set current CPU count for {vm_name}')
            return False
        self.log.info(f'Successfully set current CPU count for {vm_name} to {cpu}')
        return True

    def __shutdown_vm_if_running(self, vm_name: str, force: bool = False) -> tuple:
        """Helper function to check if a VM is running and shutdown if it is. Will prompt the user to shutdown the VM
        if force is False. Sets the running state to True if the VM is running so it can be referenced after action
        is performed to power back on if need be.

        Args:
            vm_name (str): vm name to check if running
            force (bool, optional): force shutdown operation without prompt. Defaults to False.

        Returns:
            tuple: (bool, bool) state, running state
        """
        running = False
        if vm_name in self.get_instances().get('running', []):
            running = True
            if force or input(f'VM {vm_name} is running. Shutdown? [y/n]: ').lower() == 'y':
                if not self.shutdown_vm(vm_name):
                    return False, running
            else:
                self.log.error(f'VM {vm_name} is running. Cannot change resources')
                return False, running
        return True, running

    def _wait_for_vm_init(self, vm_name: str, max_wait: int = 120) -> str:
        """Wait for a VM to initialize by checking the state of the VM every 5 seconds. If the VM is not initialized
        after max_wait seconds, it will return False. When the VM is initialized, it will display the IP address
        for interface 1 of the VM and return the IP address.

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
        """List all VMs on the hypervisor. This will display the VMs in JSON format.

        Returns:
            bool: True if successful, False otherwise
        """
        return self.display_info_msg(f'VMs:\n{json.dumps(self.get_instances(True), indent=2)}')

    def delete_vm(self, vm_name: str, force: bool = False) -> bool:
        """Delete a VM by shutting it down, undefine it, and deleting its directory. This will remove all traces of
        the VM from the hypervisor and the VM directory.

        Args:
            vm_name (str): The name of the VM to delete
            force (bool, optional): Force the delete without user input. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if force or input(f'Delete VM {vm_name} and all its data? [y/n]: ').lower() == 'y':
            self.log.info(f'Deleting VM {vm_name}')
            instance = self.get_instances()
            if self.__instance_exists(vm_name, instance):
                if vm_name in instance.get('running', []):
                    if not self.shutdown_vm(vm_name):
                        return False
                if not self.__undefine_vm(vm_name):
                    return False
            return self.__delete_vm_directory(vm_name)
        return False

    def shutdown_vm(self, vm_name: str, max_wait: int = 60) -> bool:
        """Shutdown a VM using the virsh shutdown command. It will wait for the VM to shutdown for max_wait seconds
        then force shutdown the VM if it is not shutdown.

        Args:
            vm_name (str): the name of the VM to shutdown
            max_wait (int, optional): the max wait time for VM shutdown. Defaults to 60 (1 min).

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
            return self.__wait_for_vm_shutdown(vm_name, max_wait)
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

    def start_vm(self, vm_name: str, max_wait: int = 120) -> str:
        """Start a VM using the virsh start command then wait for the VM to initialize and return the IP address.
        It will wait a maximum of max_wait seconds for the VM to initialize before giving up.

        Args:
            vm_name (str): the name of the VM to start
            max_wait (int, optional): the max wait time for VM initialization. Defaults to 120 (2 mins).

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
            return self._wait_for_vm_init(vm_name, max_wait)
        self.log.error(f'Failed to start VM {vm_name}')
        return ''

    def soft_reset_vm(self, vm_name: str) -> bool:
        """Soft reset a VM by shutting it down gracefully and starting it back up. If the VM is not running,
        it will be started. If the reset fails it will be forced to shutdown then restarted.

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
        """Purge VM images and delete all images for non running VMs.

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
        """Get all instances on the hypervisor. This will return a dictionary of instances with the state as the key

        Args:
            sort (bool, optional): option to sort the VMs within their state key. Defaults to False.

        Returns:
            dict: dictionary of instances with the state as the key and a list of VM names as the value
        """
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
        """Check if a VM is running using the virsh dominfo command.

        Args:
            vm_name (str): name of the vm to check if it is running

        Returns:
            bool: True if the VM is running, False otherwise
        """
        return self.__get_vm_state(vm_name) == 'running'

    def is_vm_stopped(self, vm_name: str) -> bool:
        """Check if a VM is stopped using the virsh dominfo command.

        Args:
            vm_name (str): name of the vm to check if it is stopped

        Returns:
            bool: True if the VM is stopped, False otherwise
        """
        return self.__get_vm_state(vm_name) == 'shut off'

    def is_vm_paused(self, vm_name: str) -> bool:
        """Check if a VM is paused using the virsh dominfo command.

        Args:
            vm_name (str): name of the vm to check if it is paused

        Returns:
            bool: True if the VM is paused, False otherwise
        """
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

    def get_vm_disk_capacity(self, vm_name: str, disk_name: str) -> int:
        """Get the disk capacity of a VM using the virsh domblkinfo command. This will return the disk capacity in
        bytes.

        Args:
            vm_name (str): name of the vm to get the disk capacity for
            disk_name (str): name of the disk to get the capacity for

        Returns:
            int: disk capacity in bytes or 0 if not found
        """
        rsp = self._run_cmd(f'virsh domblkinfo {vm_name} {disk_name}')
        if rsp[1]:
            for line in rsp[0].splitlines():
                if 'Capacity:' in line:
                    try:
                        return int(line.split(':')[-1].strip())
                    except Exception:
                        self.log.exception(f'Failed to convert disk capacity to int for {disk_name} on {vm_name}')
                        return 0
        self.log.error(f'Failed to get disk capacity for {disk_name} on {vm_name}')
        return 0

    def get_vm_disks(self, vm_name: str) -> dict:
        """Get the disks attached to a VM using the virsh domblklist command. It will return a dictionary of disks with
        target as the key and a dict of location, serial, and size as the value.

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
                    size = self.get_vm_disk_capacity(vm_name, info[0])
                    disks[info[0]] = {
                        'location': info[1],
                        'serial': f'{vm_name}-{info[1].split("/")[-1].split(".")[0]}',
                        'size_bytes': size,
                        'size': self.__bytes_to_human_readable(size),
                    }
        return disks

    def eject_instance_iso(self, vm_name: str, remove_cdrom: bool = True) -> bool:
        """Eject the attached ISO from a VM using the virsh change-media command. This will eject the ISO from the VM
        and remove the CDROM device from the VM if specified.

        Args:
            vm_name (str): name of the vm to eject the ISO from
            remove_cdrom (bool, optional): option to delete cdrom device from VM after being ejected. Defaults to True.

        Returns:
            bool: True if successful, False otherwise
        """
        disks: dict = self.get_vm_disks(vm_name)
        for target, source in disks.items():
            if source.get('location', '').endswith('.iso'):
                if self._run_cmd(f'virsh change-media {vm_name} {target} --eject --config')[1]:
                    self.log.info(f'Ejected {source.get("location")} from {vm_name}')
                    if remove_cdrom:
                        return self.__remove_instance_cdrom(vm_name, target)
                    return True
        self.log.error(f'Failed to remove attached iso from {vm_name}')
        return False

    def create_data_disk(self, vm_name: str, size: int | str, name: str = 'GENERATE', filesystem: str = 'ext4',
                         mount: str = 'default') -> bool:
        """Create a data disk for a VM and attach it. This will also run a playbook to format and mount the disk

        Args:
            vm_name (str): name of the VM to create the disk for
            size (int | str): size of the disk to create. Can be a number or a string with a suffix (k, m, g, t)
            name (str, optional): name to give to the data disk. Defaults to 'GENERATE'.
            filesystem (str, optional): filesystem to create on the data disk. Defaults to 'ext4'.
            mount (str, optional): location to mount the disk. Default is /mnt/disk-name. Defaults to 'default'.

        Returns:
            bool: True if successful, False otherwise
        """
        disk_name = self.__create_data_disk(vm_name, size, name)
        if disk_name:
            vms = self.get_instances()
            if self.__attach_data_disk(vm_name, disk_name, vms):
                if vm_name in vms.get('running', []):
                    device_name = disk_name.split('/')[-1].split('.')[0]
                    mount = mount if mount != 'default' else f'/mnt/{device_name}'
                    ip = self.get_vm_ip_by_index(vm_name)
                    if ip:
                        data = {'device_name': device_name, 'filesystem': filesystem, 'mount': mount}
                        if self.run_ansible_playbook(ip, vm_name, 'format_and_mount_data_disk.yml', data):
                            self.log.info(f'Successfully formatted and mounted {disk_name} on {vm_name}')
                            return True
                    else:
                        self.log.error(f'Failed to get IP address to run ansible playbook on {vm_name}')
                        return False
                self.log.info(f'Successfully attached {disk_name} to {vm_name}, but did not format or mount it')
                return True
        return False

    def get_vm_interfaces(self, vm_name: str) -> dict:
        """Get the interfaces attached to a VM using the virsh guestinfo command. It will return a dictionary of
        VM interfaces with the interface number as the key and a dict of name, mac, ip, and subnet as the value.

        Args:
            vm_name (str): name of the vm to get the interfaces for

        Returns:
            dict: vm interfaces dict
        """
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
                        interfaces[num]['mac'] = value
                    elif '0.addr' in key:
                        interfaces[num]['ip'] = value
                    elif '0.prefix' in key:
                        interfaces[num]['subnet'] = '/' + value
        return interfaces

    def get_eth_interfaces(self, vm_name: str) -> dict:
        """Gets the VM interfaces then parses the data to pull either the eth or enp interfaces

        Args:
            vm_name (str): name of the vm to get the interfaces for

        Returns:
            dict: vm interfaces dict
        """
        eth = {}
        interfaces = self.get_vm_interfaces(vm_name)
        for num, interface in interfaces.items():
            if interface.get('name', '').startswith(('eth', 'enp')):
                eth[num] = interface
        return eth

    def display_vm_interfaces(self, vm_name: str, instances: dict = None) -> str:
        """Display the interfaces of a VM. If the VM Is powered on then it uses the virsh guestinfo command. If
        the VM is powered off then it uses the virsh dumpxml command to get the interfaces. Info is displayed in JSON

        Args:
            vm_name (str): name of the vm to get the interfaces for
            instances (dict, optional): instances of the hypervisor. Defaults to None and will pull

        Returns:
            str: JSON formatted string of the VM interfaces
        """
        if not instances:
            instances = self.get_instances()
        if vm_name in instances.get('running', []):
            return self.display_info_msg(json.dumps(self.get_eth_interfaces(vm_name), indent=2))
        return self.display_info_msg(json.dumps(self.__get_shutdown_vm_interfaces(vm_name), indent=2))

    def get_vm_ip_by_index(self, vm_name: str, network_index: int = 1) -> str:
        """Get the IP address of a VM using the virsh guestinfo command. This will return the IP address of the VM
        for the specified network index. If the IP address is not found, it will return None.

        Args:
            vm_name (str): name of the vm get the interface IP address
            network_index (int, optional): network index to get IP address. Defaults to 1.

        Returns:
            str: IP address of the VM or empty string if not found
        """
        interfaces = self.get_vm_interfaces(vm_name)
        if str(network_index) in interfaces:
            return interfaces[str(network_index)].get('ip', '')
        return ''

    def add_network_interface(self, vm_name: str) -> bool:
        """Attach a network interface to a VM using the virsh attach-device command. It creates an xml config file
        to add the network device to the VM. It will delete the config file after the device is added. It wait for
        the VM to populate the IP address (~15 seconds) before displaying the interface data if the VM is powered on.
        Displays the interface data after the device is added.

        Args:
            vm_name (str): name of the vm to attach the network interface to

        Returns:
            bool: True if successful, False otherwise
        """
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return False
        network_file = self.__create_add_network_file(vm_name)
        if network_file and self.__attach_device(vm_name, network_file, instances):
            if self.__remove_config_file(network_file):
                if vm_name in instances.get('running', []):
                    sleep(15)  # give time for IP address to populate
                self.log.info(f'Successfully attached network interface to {vm_name}')
                return self.display_vm_interfaces(vm_name, instances)
        self.log.error(f'Failed to attach network interface to {vm_name}')
        return False

    def remove_network_interface(self, vm_name: str, mac: str) -> bool:
        """Detach a network interface from a VM using the virsh detach-device command. It creates an xml config file
        to remove the network device from the VM. It will delete the config file after the device is removed.
        Displays the interface data after the device is removed.

        Args:
            vm_name (str): _description_
            mac (str): _description_

        Returns:
            bool: _description_
        """
        instances = self.get_instances()
        if not self.__instance_exists(vm_name, instances):
            self.log.error(f'VM {vm_name} does not exist')
            return False
        network_file = self.__create_remove_network_file(vm_name, mac)
        if network_file and self.__detach_device(vm_name, network_file, instances):
            if self.__remove_config_file(network_file):
                self.log.info(f'Successfully removed network interface from {vm_name}')
                return self.display_vm_interfaces(vm_name, instances)
        self.log.error(f'Failed to attach network interface to {vm_name}')
        return False

    def display_vm_disks(self, vm_name: str) -> bool:
        """Display the disks attached to a VM using the virsh domblklist command. Data is displayed in JSON format.

        Args:
            vm_name (str): name of the vm get the disks for

        Returns:
            bool: True if successful, False otherwise
        """
        return self.display_info_msg(json.dumps(self.get_vm_disks(vm_name), indent=2))

    def unmount_system_disk(self, vm_name: str, device: str) -> bool:
        """Unmount a system disk from a VM using the ansible playbook. This will run the unmount_disk.yml playbook

        Args:
            vm_name (str): name of the VM to unmount the disk from
            device (str): disk device to unmount (ex: sda, sdb)

        Returns:
            bool: True if successful, False otherwise
        """
        if device == 'sda':
            self.log.error('Cannot unmount system boot disk')
            return False
        disks = self.get_vm_disks(vm_name)
        if device in disks:
            if vm_name in self.get_instances().get('running', []):
                return self.__unmount_system_disk(vm_name, device, disks)
            self.log.error(f'VM {vm_name} is not running')
        else:
            self.log.error(f'Disk {device} not found on {vm_name}')
        return False

    def mount_system_disk(self, vm_name: str, device: str, mount: str) -> bool:
        """Mount a system disk to a VM using the ansible playbook. This will run the mount_disk.yml playbook

        Args:
            vm_name (str): name of the VM to mount the disk to
            device (str): disk device to mount (ex: sda, sdb)
            mount (str): location to mount the disk (ex: /mnt/disk-name)

        Returns:
            bool: True if successful, False otherwise
        """
        if device == 'sda':
            self.log.error('Cannot mount system boot disk')
            return False
        disks = self.get_vm_disks(vm_name)
        if device in disks:
            device_name = disks[device].get('location', '').split("/")[-1].split(".")[0]
            mount = mount if mount != 'default' else f'/mnt/{device_name}'
            if vm_name in self.get_instances().get('running', []):
                return self.__mount_system_disk(vm_name, device_name + '-part1', mount)
            self.log.error(f'VM {vm_name} is not running')
        else:
            self.log.error(f'Disk {device} not found on {vm_name}')
        return False

    def remove_data_disk(self, vm_name: str, device: str, force: bool = False):
        """Remove a data disk from a VM using the virsh detach-device command. It creates an xml config file to remove
        the device then, removes the disk then deletes the config file. Deletes the physical disk if force is True or
        prompted by the user.

        Args:
            vm_name (str): name of the VM to remove the disk from
            device (str): disk device to remove (ex: sda, sdb)
            disks (dict): dictionary of disks with the target as the key and the source as the value
            vms (dict): dictionary of VMs with the state as the key and a list of VM names as the value

        Returns:
            bool: True if successful, False otherwise
        """
        if device == 'sda':
            self.log.error('Cannot remove system boot disk')
            return False
        disks = self.get_vm_disks(vm_name)
        if device in disks:
            vms = self.get_instances()
            if vm_name in vms.get('running', []):
                if not self.__unmount_system_disk(vm_name, device, disks):
                    return False
            if not self.__remove_data_disk(vm_name, device, disks, vms):
                return False
            if force or input(f'Delete disk {disks[device]["location"]} from {vm_name}? [y/n]: ').lower() == 'y':
                return self.__delete_vm_disk(disks[device]['location'])
        self.log.error(f'Disk {device} not found on {vm_name}')
        return False

    def set_disk_size(self, vm_name: str, device: str, size: int | str, force: bool = False) -> bool:
        """Set the size of a VM disk using the qemu-img resize command. This will set the size of the disk to the
        specified size.

        Args:
            vm_name (str): name of the vm to set the disk size
            device (str): name of the disk to set the size
            size (int | str): new size of the disk in bytes or human readable format (ex: 10G)
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if self.__validate_disk_change(vm_name, force):
            size_bytes = self.__convert_size_to_bytes(size)
            if size_bytes and self._run_cmd(f'qemu-img resize {device} {size_bytes}')[1]:
                self.log.info(f'Successfully set disk {device} to {size}')
                return True
            self.log.error(f'Failed to increase disk {device}')
        return False

    def increase_disk_size(self, vm_name: str, device: str, size: int | str, force: bool = False) -> bool:
        """Increase the size of a VM disk using the qemu-img resize command. Runs ansible playbook to resize the disk
        partition and filesystem on the VM.

        Args:
            vm_name (str): name of the vm to increase the disk size
            device (str): name of the disk to increase the size
            size (int | str): new size of the disk in bytes or human readable format (ex: 10G)
            force (bool, optional): power off the VM without prompt if powered on. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        disks = self.get_vm_disks(vm_name)
        if device in disks:
            if self.__increase_disk_size(vm_name, disks[device]["location"], size, force):
                ip = self.start_vm(vm_name)
                if ip:
                    suffix = '-part1' if device != 'sda' else ''
                    device_name = f'{vm_name}-{disks[device]["location"].split("/")[-1].split(".")[0]}{suffix}'
                    if self.run_ansible_playbook(ip, vm_name, 'resize_disk.yml', {'device_name': device_name}):
                        self.log.info(f'Successfully resized disk {device} on {vm_name}')
                        return True
                    self.log.error(f'Failed to resize disk {device} on {vm_name}')
        else:
            self.log.error(f'Disk {device} not found on {vm_name}')
        return False

    def get_vm_resources(self, vm_name: str) -> dict:
        """Get the resources of a VM using the virsh dominfo command. This will return a dictionary of resources
        with the name as the key and the value as the value.

        Args:
            vm_name (str): name of the vm to get the resources for

        Returns:
            dict: dictionary of resources with the name as the key and the value as the value
        """
        resources = {}
        rsp = self._run_cmd(f'virsh domstats {vm_name}')
        if rsp[1]:
            for line in rsp[0].splitlines():
                if 'vcpu.current=' in line:
                    resources['cpu'] = int(line.split('=')[-1].strip())
                if 'balloon.current=' in line:
                    size = self.__convert_size_to_bytes(line.split('=')[-1].strip() + 'kb')
                    resources['memory_bytes'] = size
                    resources['memory'] = self.__bytes_to_human_readable(size)
        return resources

    def display_resources(self, vm_name: str) -> bool:
        """Display the CPU and memory resources of a VM. Displays data in JSON format

        Args:
            vm_name (str): name of the vm to get the resources for

        Returns:
            bool: True if successful, False otherwise
        """
        return self.display_info_msg(json.dumps(self.get_vm_resources(vm_name), indent=2))

    def set_vm_resources(self, vm_name: str, cpu: int = 0, memory: int = 0, force: bool = False) -> bool:
        """Set the CPU and memory resources of a VM using the virsh setvcpus and virsh setmem commands. VM
        needs to be powered off to update these resources so it will check if the VM is running and shutdown.
        The VM will be powered back on after the resources are set.

        Args:
            vm_name (str): name of the vm to set the resources for
            cpu (int, optional): cpu change qty to set. Defaults to 0.
            memory (int, optional): memory change to set. Defaults to 0.
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        state, running = self.__shutdown_vm_if_running(vm_name, force)
        if state:
            updated = False
            if self.__set_vm_cpu(vm_name, cpu) and self.__set_vm_memory(vm_name, memory):
                self.log.info(f'Successfully set resources for {vm_name}')
                updated = True
            if running and not self.start_vm(vm_name):
                return False
            return updated
        return False

from pathlib import Path
from logging import Logger
from os import remove
from shutil import copy2

from kvm_2_gcp.utils import Utils
from kvm_2_gcp.kvm_controller import KVMController


class KVMImages(Utils):
    def __init__(self, logger: Logger = None):
        """KVM Images class to manage KVM images (local images)

        Args:
            logger (Logger, optional): logging object to use. Defaults to None.
        """
        super().__init__(logger)

    @property
    def controller(self) -> KVMController:
        """KVM controller object to control KVM

        Returns:
            KVMController: KVM controller object
        """
        return KVMController(self.log)

    def list_images(self) -> bool:
        """List all images in the image directory

        Returns:
            bool: True if images are found, False otherwise
        """
        ignore_list = ['__init__.py', 'cache.json']
        images = []
        for image in Path(self.image_dir).iterdir():
            image_name = image.name
            if image_name not in ignore_list and not image_name.endswith('.json'):
                images.append(image_name)
        if images:
            images.sort()
            msg = 'Images:\n  ' + '\n  '.join(images)
            return self.display_info_msg(msg)
        return self.display_warning_msg('No images found')

    def delete_image(self, image_name: str, force: bool = False) -> bool:
        """Delete an image from the image directory

        Args:
            image_name (str): name of the image to delete
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if image is deleted, False otherwise
        """
        image_file = Path(f'{self.image_dir}/{image_name}')
        if image_file.exists():
            if force or input(f'Delete image {image_name}? [y/n] ').lower() == 'y':
                try:
                    remove(image_file)
                    self.log.info(f'Deleted image {image_name}')
                    return True
                except Exception:
                    self.log.exception(f'Failed to delete image {image_name}')
            return False
        return self.display_fail_msg(f'Image {image_name} not found')

    def __validate_boot_disk_clone(self, vm_name: str, force: bool = False) -> Path | None:
        """Checks if the VM boot disk exists and if the VM is running. If the VM is running, it will try to
        shutdown the VM. Will return the boot disk if successful found and vm is shutdown.

        Args:
            vm_name (str): name of the VM to check
            force (bool, optional): force operation. Defaults to False.

        Returns:
            Path | None: Path to the boot disk if found, None otherwise
        """
        vm_boot_disk = Path(f'{self.vm_dir}/{vm_name}/boot.qcow2')
        if not vm_boot_disk.exists():
            self.log.error(f'VM {vm_name} boot disk does not exist')
            return None
        if self.controller.is_vm_running(vm_name):
            if force or input(f'VM {vm_name} is running. Shutdown VM? [y/n] ').lower() == 'y':
                if not self.controller.shutdown_vm(vm_name):
                    self.log.error(f'Failed to shutdown VM {vm_name}')
                    return None
            else:
                return None
        return vm_boot_disk

    def __validate_image_clone(self, image_name: str) -> Path | None:
        """Checks if the image name is valid and if the image already exists. Returns the image Path if valid.

        Args:
            image_name (str): name of the image to check

        Returns:
            Path | None: Path to the image if valid, None otherwise
        """
        if not image_name.endswith(('.qcow2', '.img')):
            image_name += '.qcow2'
        image_file = Path(f'{self.image_dir}/{image_name}')
        if image_file.exists():
            self.log.error(f'Image {image_name} already exists')
            return None
        return image_file

    def create_clone(self, vm_name: str, image_name: str, force: bool = False) -> bool:
        """Create a clone of a VM by copying the boot disk to the image directory. Will power down the VM if
        running

        Args:
            vm_name (str): name of the VM to clone
            image_name (str): name of the image to create
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if image is created, False otherwise
        """
        image_name = image_name if image_name != 'GENERATE' else f'image-{vm_name}.qcow2'
        image_file = self.__validate_image_clone(image_name)
        if image_file:
            vm_boot_disk = self.__validate_boot_disk_clone(vm_name, force)
            if vm_boot_disk:
                try:
                    copy2(vm_boot_disk, image_file)
                    return True
                except Exception:
                    self.log.exception(f'Failed to create image {image_file} from VM {vm_name}')
        return False

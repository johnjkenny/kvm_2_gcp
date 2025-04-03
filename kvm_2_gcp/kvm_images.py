from pathlib import Path
from logging import Logger
from os import remove
from shutil import copy2

from kvm_2_gcp.utils import Utils
from kvm_2_gcp.kvm_controller import KVMController


class KVMImages(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)

    @property
    def controller(self):
        return KVMController(self.log)

    def list_images(self):
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

    def delete_image(self, image_name: str, force: bool = False):
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
        if not image_name.endswith('.qcow2'):
            image_name += '.qcow2'
        image_file = Path(f'{self.image_dir}/{image_name}')
        if image_file.exists():
            self.log.error(f'Image {image_name} already exists')
            return None
        return image_file

    def create_clone(self, vm_name: str, image_name: str, force: bool = False):
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

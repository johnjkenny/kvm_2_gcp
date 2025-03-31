from pathlib import Path
from logging import Logger
from os import remove

from kvm_2_gcp.utils import Utils


class KVMImages(Utils):
    def __init__(self, logger: Logger = None):
        super().__init__(logger)

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

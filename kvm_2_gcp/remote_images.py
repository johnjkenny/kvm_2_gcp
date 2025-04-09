import json
from re import match as re_match
from hashlib import sha256
from logging import Logger
from pathlib import Path
from os import remove

import requests
from bs4 import BeautifulSoup
from google.cloud import compute_v1

from kvm_2_gcp.utils import Utils
from kvm_2_gcp.gcp_controller import GCPController


class Web():
    def __init__(self, logger: Logger):
        """Web module to handle web requests and content streaming to download files

        Args:
            logger (Logger): logger object to use for logging
        """
        self.log = logger

    def stream_web_content(self, url: str, chunk_size: int = 3145728):
        """Stream the web content from the url

        Args:
            url (str): the http/https web url to get content for
            chunk_size (int, optional): the chunk size to stream. Defaults to 3145728 (3MB).

        Yields:
            bytes: the web content in chunks
        """
        rsp = requests.get(url, stream=True)
        if rsp.status_code == 200:
            for chunk in rsp.iter_content(chunk_size):
                yield chunk
        else:
            self.log.error(f'Failed to fetch URL content. [{rsp.status_code}]: {rsp.reason}')

    def get_content(self, url: str, return_type: str = 'text') -> str | bytes:
        """Get url web content using requests.get method. Log any non 200 return codes with return code and reason

        Args:
            url (str): the http/https web url to get content for
            return_type (str, optional): the return type. Defaults to 'text'. Options: 'text', 'bytes'

        Returns:
            str or bytes: the web content pulled or empty string on failure
        """
        rsp: requests.Response = requests.get(url)
        if rsp.status_code == 200:
            if return_type == 'text':
                return rsp.text
            return rsp.content
        self.log.error(f'Failed to fetch URL content. [{rsp.status_code}]: {rsp.reason}')
        return '' if return_type == 'text' else b''


class RemoteImage(Utils):
    def __init__(self, family: str = 'rocky', logger: Logger = None):
        """Remote image Parent class to handle remote image downloads and cache management.

        Args:
            family (str, optional): remote image family. Defaults to 'rocky'.
            logger (Logger, optional): logger object to use. Defaults to None.
        """
        super().__init__(logger)
        self.images = {}
        self.__family = family

    @property
    def cache_file(self) -> str:
        """Location of cache file

        Returns:
            str: path to the cache file (image_dir/family_cache.json)
        """
        return f'{self.image_dir}/{self.__family}_cache.json'

    @property
    def __family_title(self) -> str:
        """Helper to display the family name as a title

        Returns:
            str: formatted family name
        """
        if '-' in self.__family:
            _split = self.__family.split('-')
            return f'{_split[0].upper()}-{_split[1].capitalize()}'
        return self.__family.capitalize()

    def __download(self, image_file: Path, image: dict) -> bool:
        """Download the image from the url to the image path. Stream the content and write it to the image file
        and update the download progress. Set the end state and validate the download using the image size and checksum

        Returns:
            bool: True if successful, False otherwise
        """
        checksum = sha256()
        total_size = image.get('size')
        downloaded = 0
        try:
            with open(image_file, 'wb') as file:
                for chunk in Web(self.log).stream_web_content(image.get('url')):
                    if chunk:
                        file.write(chunk)
                        checksum.update(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            print(f'\rDownloading: {(downloaded / total_size) * 100:.2f}% complete', end='')
                        else:
                            print(f'\rDownloading: {downloaded} bytes downloaded', end='')
            print()
        except KeyboardInterrupt:
            self.log.info('Download interrupted by user')
            return False
        except Exception:
            self.log.exception(f'Failed to download image {image.get("name")}')
            return False
        if image.get('checksum'):
            if checksum.hexdigest() == image.get('checksum'):
                self.log.info(f'Successfully downloaded {image.get("name")}')
                return True
            self.log.error(f'Checksum mismatch for image download: {image.get("checksum")} != {checksum.hexdigest()}')
            return False
        self.log.info(f'Downloaded {image.get("name")}, but no checksum provided to validate')
        return True

    def __delete_image(self, image_file: Path, image_name: str) -> bool:
        """Delete the image file from the image path

        Args:
            image_file (Path): image file path (full path)
            image_name (str): image name

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            remove(image_file)
            return True
        except Exception:
            self.log.exception(f'Failed to delete image {image_name}')
            return False

    def __validate_image_checksum(self, image_file: Path, image: dict) -> bool:
        """Validate the image checksum. It will calculate the sha256 checksum of the image file and compare it to the
        checksum in the image object.

        Args:
            image_file (Path): image file path (full path)
            image (dict): image object to validate

        Returns:
            bool: True if checksum matches, False otherwise
        """
        checksum = sha256()
        with open(image_file, 'rb') as file:
            for chunk in iter(lambda: file.read(1048576), b''):
                if chunk:
                    checksum.update(chunk)
        if checksum:
            return image.get('checksum', '') == checksum.hexdigest()
        self.log.error(f'Failed to calculate sha256 checksum for image: {image.get("name")}')
        return False

    def __image_is_downloaded_check(self, image_file: Path, image: dict) -> bool:
        """Check if the image file exists and validate the checksum.

        Args:
            image_file (Path): image file path (full path)
            image (dict): image object to validate

        Returns:
            bool: True if image exists and checksum matches, False otherwise
        """
        if image_file.exists():
            if not self.__validate_image_checksum(image_file, image):
                self.log.info(f'Image {image.get("name")} exists, but checksum does not match')
            return True
        return False

    def _save_cache(self) -> bool:
        """Save the cache data to the cache file. It will create the cache file if it does not exists. Cache data will
        be overridden if the file exists.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.cache_file, 'w') as cache_file:
                json.dump(self.images, cache_file, indent=2)
            return True
        except Exception:
            self.log.exception('Failed to save cache file')
            return True

    def _get_image_obj_by_name(self, name: str) -> dict:
        """Get the image object by name. It will check if the image is in the cache and return it. Will load the
        cache data if not already loaded.

        Args:
            name (str): image name to lookup in cache

        Returns:
            dict: image object if found, empty dict otherwise
        """
        if not self.images and not self.load_cache():
            self.log.error('Failed to get image object by name')
            return {}
        image = self.images.get(name, None)
        if image is not None:
            return image
        self.log.info(f'Image {name} not found in cache')
        return {}

    def refresh_cache(self):
        # Placeholder for child class overwrite
        return True

    def load_cache(self, refresh: bool = False, arch: str = 'x86_64') -> bool:
        """Load the cache data from the cache file. It will check if the cache file exists and load it.

        Args:
            refresh (bool, optional): option to refresh cache from remote repository. Defaults to False.
            arch (str, optional): architecture to pull from remote repo if refresh. Defaults to 'x86_64'.

        Returns:
            bool: True if successful, False otherwise
        """
        if refresh or not Path(self.cache_file).exists():
            return self.refresh_cache(arch)
        try:
            with open(self.cache_file, 'r') as cache_file:
                self.images: dict = json.load(cache_file)
            return True
        except Exception:
            self.log.exception('Failed to load cache data')
        return False

    def display_cache(self, refresh: bool = False, arch: str = 'x86_64') -> bool:
        """Display the cache data to console.

        Args:
            refresh (bool, optional): option to refresh the cache data. Defaults to False.
            arch (str, optional): architecture to pull from remote repo if refresh. Defaults to 'x86_64'.

        Returns:
            bool: True if successful, False otherwise
        """
        if refresh or not self.images:
            if not self.load_cache(refresh, arch):
                self.log.error(f'Failed to load {self.__family} cache')
                return False
        return self.display_info_msg(f'{self.__family_title} Remote Images:\n  ' + '\n  '.join(self.images.keys()))

    def download_image(self, image_name: str, force: bool = False) -> bool:
        """Download the image from the remote repository. It will check if the image is already downloaded and
        validate the checksum. If the image is already downloaded and the checksum matches, it will not download
        the image again unless prompted to do so or force is set to True. If the image is downloaded, but the checksums
        do not match then prompt to redownload the image or force the redownload automatically.

        Args:
            image_name (str): image name to download
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        image = self._get_image_obj_by_name(image_name)
        if image:
            image_file = Path(f'{self.image_dir}/{image_name}')
            if self.__image_is_downloaded_check(image_file, image):
                if force or input(f'Image {image_name} exists. Overwrite? (y/n): ').lower() == 'y':
                    if not self.__delete_image(image_file, image_name):
                        return False
                else:
                    return True
            return self.__download(image_file, image)
        self.log.error(f'Image {image_name} not found in cache')
        return False


class RockyImages(RemoteImage):
    """Class to handle Rocky remote images"""
    def __init__(self, logger: Logger = None):
        """Rocky remote image handler. Pulls repo data to cache locally including urls to download remote images.

        Args:
            logger (Logger, optional): logger object to use. Defaults to None.
        """
        super().__init__('rocky', logger)

    def __get_cloud_versions(self, sort_versions: bool = True) -> list:
        """Get all Rocky cloud versions. It will pull all Rocky cloud versions from the Rocky download page and return
        them as a sorted list. Rocky removed some versions of their cloud images so we ignore those versions.

        Args:
            sort_versions (bool, optional): option to sort the return versions list. Defaults to True.

        Returns:
            list: list of Rocky cloud versions
        """
        versions = []
        ignore_list = ['9.4', '9.3', '9.2', '9.1', '9.0']
        repo_content = Web(self.log).get_content('https://download.rockylinux.org/pub/rocky/')
        if repo_content:
            soup = BeautifulSoup(repo_content, "html.parser")
            for link in soup.find_all('a'):
                link: dict
                href: str = link.get('href', '').strip('/')
                if href.startswith('8') or href == '9':
                    continue
                if re_match(r'^\d+(\.\d+)?$', href):
                    if href not in ignore_list:
                        versions.append(href)
        if sort_versions:
            return sorted(versions, key=lambda v: [int(part) for part in v.split('.')], reverse=True)
        return versions

    def __update_cloud_cache_data(self, version: str, arch: str = 'x86_64') -> bool:
        """Create Rocky cloud image objects. It will pull the Rocky cloud checksum file which contains
        the image name, size and checksum. Adds the image objects to the images dict.

        Args:
            version (str): the version of the image to pull
            arch (str, optional): the architecture the image should be installed on. Defaults to 'x86_64'.

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Pulling Rocky {version}.{arch} remote images')
        arch_url = f'https://download.rockylinux.org/pub/rocky/{version}/images/{arch}'
        contents = Web(self.log).get_content(f'{arch_url}/CHECKSUM')
        if contents:
            image = {}
            for line in contents.splitlines():
                if line.startswith('#'):
                    line_split = line.split()
                    name = line_split[1].replace(':', '')
                    image = {'name': name, 'size': int(line_split[2]), 'checksum': None, 'url': f'{arch_url}/{name}',
                             'version': version, 'arch': arch}
                elif line.startswith('SHA256') and image:
                    image['checksum'] = line.split()[-1]
                    self.images[name] = image
                    image = {}
            return True
        else:
            self.log.error(f'Failed to get rocky cloud checksum file for version: {version}')
        return False

    def refresh_cache(self, arch: str = 'x86_64') -> bool:
        """Refresh the Rocky cloud cache. It will pull all new Rocky cloud images for all versions for the specified
        architecture.

        Args:
            arch (str, optional): the architecture to pull cache data for. Defaults to 'x86_64'.

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info('Refreshing Rocky cloud image cache data')
        self.images = {}
        for version in self.__get_cloud_versions():
            if not self.__update_cloud_cache_data(version, arch):
                self.log.error('Failed to refresh Rocky cloud image cache data')
                return False
        return self._save_cache()


class UbuntuImages(RemoteImage):
    def __init__(self, logger: Logger = None):
        """Ubuntu remote image handler. Pulls repo data to cache locally including urls to download remote images.

        Args:
            logger (Logger, optional): logging object to use. Defaults to None.
        """
        super().__init__('ubuntu', logger)

    def __get_cloud_versions(self, sort_versions: bool = True) -> list:
        """Get all Ubuntu cloud versions that are not EOL.

        Args:
            sort_versions (bool, optional): option to sort version sata. Defaults to True.

        Returns:
            list: list of Ubuntu cloud versions
        """
        versions = []
        repo_content = Web(self.log).get_content('https://cloud-images.ubuntu.com/releases/')
        if repo_content:
            soup = BeautifulSoup(repo_content, "html.parser")
            for link in soup.find_all('a', href=True):
                link: dict
                href = link["href"].strip("/")
                if not href.replace(".", "").isdigit():
                    continue
                text_after = link.next_sibling
                if 'END OF LIFE' in text_after or 'END OF REGULAR SUPPORT' in text_after:
                    continue
                versions.append(href)
        if sort_versions:
            versions.sort()
        return versions

    def __update_cloud_cache_data(self, version: str, arch: str = 'amd64') -> bool:
        """Create Ubuntu cloud image objects. It will pull the Ubuntu cloud checksum file which contains
        the image name, size and checksum. Adds the image objects to the images dict.

        Args:
            version (str): the version of the image to pull
            arch (str, optional): the architecture to pull cache data for. Defaults to 'amd64'.

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Pulling Ubuntu {version}.{arch} remote images')
        latest_url = f'https://cloud-images.ubuntu.com/releases/{version}/release'
        contents = Web(self.log).get_content(f'{latest_url}/SHA256SUMS')
        if contents:
            for line in contents.splitlines():
                if f'{arch}.img' in line:
                    line_split = line.split()
                    name = line_split[1].replace('*', '')
                    self.images[name] = {'name': name, 'checksum': line_split[0], 'url': f'{latest_url}/{name}',
                                         'version': version, 'arch': arch}
            return True
        else:
            self.log.error(f'Failed to get rocky cloud checksum file for version: {version}')
        return False

    def refresh_cache(self, arch: str = 'amd64') -> bool:
        """Refresh the Ubuntu cloud cache. It will pull all new Ubuntu cloud images for all versions for the specified
        architecture.

        Args:
            arch (str, optional): the architecture to pull cache data for. Defaults to 'amd64'.

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info('Refreshing Ubuntu cloud image cache data')
        self.images = {}
        for version in self.__get_cloud_versions():
            if not self.__update_cloud_cache_data(version, arch):
                self.log.error('Failed to refresh Rocky cloud image cache data')
                return False
        return self._save_cache()


class GCPImages(GCPController):
    def __init__(self, project_id: str = 'default'):
        """GCP remote image handler. Pulls repo data to cache locally

        Args:
            project_id (str): GCP project ID to use for image operations. Defaults to 'default'.
        """
        super().__init__()
        self.project_id = project_id if project_id != 'default' else self._load_default_project_id()

    @property
    def public_image_info(self) -> dict:
        """A sample of public image info to display. This is a static list of public images that are available in GCP.

        Returns:
            dict: dictionary of public image projects and families
        """
        return {
            'debian-cloud': 'debian-12',
            'ubuntu-os-cloud': 'ubuntu-2404-lts-amd64',
            'rocky-linux-cloud': 'rocky-linux-9-optimized-gcp',
            'cos-cloud': 'cos-117-lts',
        }

    def __save_cache(self, family: str, images: list) -> bool:
        """ Save the cache data to the cache file. It will create the cache file if it does not exists. Cache data will
        be overridden if the file exists.

        Args:
            family (str): family name to save cache for
            images (list): list of images to save to cache

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(f'{self.image_dir}/{family}_cache.json', 'w') as cache_file:
                json.dump(images, cache_file, indent=2)
                return True
        except Exception:
            self.log.exception('Failed to save cache file')
            return False

    def __load_cache(self, family: str) -> list:
        """ Load the cache data from the cache file. It will check if the cache file exists and load it.

        Args:
            family (str): family name to load cache for

        Returns:
            list: list of images in the cache
        """
        try:
            with open(f'{self.image_dir}/{family}_cache.json', 'r') as cache_file:
                return json.load(cache_file)
        except Exception:
            self.log.exception('Failed to load cache file')
            return []

    def __create_image_obj(self, zone: str, vm_name: str, image_name: str,
                           family: str = None) -> compute_v1.Image | None:
        """Create image object from instance. It will get the boot disk from the instance and create an image object
        with the source disk.

        Args:
            zone (str): zone to get instance from
            vm_name (str): name of the instance to get
            image_name (str): name of the image to create
            family (str, optional): family name to take the image. Defaults to None.

        Returns:
            compute_v1.Image: Image object or None if not found
        """
        instance = self.get_instance(self.project_id, zone, vm_name)
        if instance:
            boot_disk = next(disk for disk in instance.disks if disk.boot)
            image = compute_v1.Image(name=image_name, source_disk=boot_disk.source)
            if family:
                image.family = family
            return image
        return None

    def get_latest_image(self, family_name: str) -> compute_v1.Image | None:
        """Get latest image for the family name.

        Args:
            family_name (str): family name to get latest image for

        Returns:
            compute_v1.Image: latest image object or None if not found
        """
        return self.image_client.get_from_family(project=self.project_id, family=family_name)

    def get_image(self, image_name: str) -> compute_v1.Image | None:
        """Get image by name.

        Args:
            image_name (str): image name to get

        Returns:
            compute_v1.Image: image object or None if not found
        """
        return self.image_client.get(project=self.project_id, image=image_name)

    def list_images_from_family(self, family: str, refresh: bool = False) -> list:
        """List images from family. It will check if the cache file exists and load it. If the cache file does not exits
        then it will pull the images from GCP and save them to the cache file. If refresh is set to True, it will always
        pull the images from GCP and save them to the cache file.

        Args:
            family (str): family name to get images for
            refresh (bool, optional): option to refresh local data. Defaults to False.

        Returns:
            list: list of images in the family
        """
        cache_file = Path(f'{self.image_dir}/{family}_cache.json')
        if refresh or not cache_file.exists():
            images = []
            for image in self.image_client.list(project=self.project_id):
                if image.family and image.family.startswith(family):
                    images.append(image.name)
            if images:
                self.__save_cache(family, images)
            return images
        return self.__load_cache(family)

    def display_images(self, family_name: str, refresh: bool = False) -> bool:
        """Display images from family. It will check if the cache file exists and load it. If the cache file does not
        exits then it will pull the images from GCP and save them to the cache file. If refresh is set to True, it will
        always pull the images from GCP and save them to the cache file.

        Args:
            family_name (str): family name to get images for
            refresh (bool, optional): option to fresh cache data. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        return self.display_info_msg(f'GCP {family_name}:\n  ' + '\n  '.join(self.list_images_from_family(family_name,
                                                                                                          refresh)))

    def display_public_image_info(self) -> bool:
        """Display public image info from static dictionary for popular image types

        Returns:
            bool: True if successful, False otherwise
        """
        max_key_len = max(len(k) for k in self.public_image_info)
        self.display_info_msg('Project'.ljust(max_key_len) + ' Family')
        for project, family in self.public_image_info.items():
            self.display_info_msg(f'{project.ljust(max_key_len)} {family}')
        return True

    def create_clone(self, zone: str, vm_name: str, image_name: str, family: str = None,
                     force: bool = False) -> bool:
        """Create an image clone of an instance boot disk. Stops the instance if it is running and creates an image
        from the boot disk. It will wait for the global operation to complete and return True if successful.

        Args:
            zone (str): zone the instance is in
            vm_name (str): name if the instance to clone
            image_name (str): name of the image to create
            family (str, optional): family name to tag image with. Defaults to None.
            force (bool, optional): force operation. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        image_name = image_name if image_name != 'GENERATE' else f'image-{vm_name}'
        if vm_name in self.get_running_instances(self.project_id, zone):
            if force or input(f'Instance {vm_name} is running. Stop it? (y/n): ').lower() == 'y':
                if not self.stop_instance(self.project_id, zone, vm_name):
                    self.log.error(f'Failed to stop GCP instance {vm_name}')
                    return False
            else:
                self.log.error(f'Instance {vm_name} is running. Cannot create image')
                return False
        image = self.__create_image_obj(zone, vm_name, image_name, family)
        if image and self.image_client is not None:
            try:
                operation = self.image_client.insert(project=self.project_id, image_resource=image)
            except Exception:
                self.log.exception('Failed to create GCP image')
                return False
            return self._wait_for_global_operation(operation)
        return False

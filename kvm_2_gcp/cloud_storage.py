import json
import pickle
from pathlib import Path
from os import remove
from logging import Logger

from google.cloud import storage
from google.api_core.exceptions import NotFound
from google.oauth2 import service_account

from kvm_2_gcp.encrypt import Cipher
from kvm_2_gcp.color import Color
from kvm_2_gcp.logger import get_logger


class GCPCloudStorage():
    def __init__(self, bucket: str = 'default', service_account: str = 'default', set_used_bucket: bool = True,
                 logger: Logger = None):
        """GCP Cloud Storage manager

        Args:
            bucket (str, optional): bucket name to use. Defaults to 'default' and will pull the default bucket name.
            service_account (str, optional): service account to use. Defaults to 'default' and will pull default SA.
            set_used_bucket (bool, optional): option to add bucket to used bucket tracker. Defaults to True.
        """
        self.log = logger or get_logger('gcp-storage')
        self.service_account = service_account
        self.__bucket = bucket
        self.__client: storage.Client | None = None
        self.__cipher: Cipher | None = None
        if set_used_bucket and bucket != 'default':
            self._add_bucket_to_used_buckets(bucket)

    @property
    def default_sa(self) -> str:
        """Get the default service account file path

        Returns:
            str: default service account file path
        """
        return f'{Path(__file__).parent}/k2g_env/default_sa'

    @property
    def default_bucket(self) -> str:
        """Default bucket file path

        Returns:
            str: default bucket file path
        """
        return f'{Path(__file__).parent}/k2g_env/default_bucket'

    @property
    def used_buckets_file(self) -> str:
        """Get the used buckets file path

        Returns:
            str: used buckets file path
        """
        return f'{Path(__file__).parent}/k2g_env/.used_buckets'

    @property
    def sa_file(self) -> str:
        """Get the service account file path. Looks up default service account if 'default' is set

        Returns:
            str: service account file path
        """
        if self.service_account == 'default':
            self.service_account = self.__get_default_service_account()
        return f'{Path(__file__).parent}/k2g_env/keys/.{self.service_account}.sa'

    @property
    def bucket(self) -> str:
        """Get the default bucket name. Looks up default bucker if 'default' is set

        Returns:
            str: service account file path
        """
        if self.__bucket == 'default':
            self.__bucket = self.__get_default_bucket()
        return self.__bucket

    @property
    def cipher(self) -> Cipher:
        """Get the cipher object for encryption/decryption

        Returns:
            Cipher: cipher object
        """
        if self.__cipher is None:
            self.__cipher = Cipher(self.log)
        return self.__cipher

    @property
    def creds(self) -> service_account.Credentials | None:
        """Get the service account credentials object

        Returns:
            service_account.Credentials | None: service account credentials object or None on failure
        """
        try:
            with open(self.sa_file, 'rb') as file:
                __creds: dict = pickle.loads(self.cipher.decrypt(file.read(), self.cipher.load_key()))
            return service_account.Credentials.from_service_account_info(__creds)
        except Exception:
            self.log.exception('Failed to load credentials')
        return None

    @property
    def client(self) -> storage.Client | None:
        """Get the storage manager client object

        Returns:
            storage.Client | None: storage manager client object or None on failure
        """
        if self.__client is None:
            try:
                self.__client = storage.Client(credentials=self.creds)
            except Exception:
                self.log.exception('Failed to load cloud storage client')
        return self.__client

    @staticmethod
    def display_success(msg: str) -> bool:
        """Display a success message to console and return True

        Args:
            msg (str): message to display

        Returns:
            bool: True
        """
        Color().print_message(msg, 'green')
        return True

    @staticmethod
    def display_error(msg: str) -> bool:
        """Display an error message to console and return False

        Args:
            msg (str): message to display

        Returns:
            bool: False
        """
        Color().print_message(msg, 'red')
        return False

    def __get_default_service_account(self) -> str:
        """Get the default service account name

        Returns:
            str: default service account name or empty string if failed
        """
        try:
            with open(self.default_sa, 'r') as file:
                return file.read().strip()
        except Exception:
            self.log.exception('Failed to load default service account')
        return ''

    def __get_default_bucket(self) -> str:
        """Get the default bucket name

        Returns:
            str: default bucket name or empty string if failed
        """
        try:
            with open(self.default_bucket, 'r') as file:
                return file.read().strip()
        except Exception:
            self.log.exception('Failed to load default service account')
        return ''

    def upload_from_file(self, file_path: str, bucket_path: str,
                         content_type: str = 'application/octet-stream') -> bool:
        """Upload file to bucket from file path

        Args:
            file_path (str): file path to upload
            bucket_path (str): the path to save the file in the bucket
            content_type (str, optional): the content type tag. Defaults to 'application/octet-stream'.

        Returns:
            bool: True if successful, False otherwise
        """
        blob = self.get_blob(bucket_path)
        if blob:
            try:
                blob.upload_from_filename(file_path, content_type=content_type)
                self.log.info(f'Successfully uploaded file {file_path} to {bucket_path}')
                return True
            except Exception:
                self.log.exception(f'Failed to upload file to {bucket_path}')
        else:
            self.log.error(f'Failed to upload file {file_path} to {bucket_path}')
        return False

    def __download_object_to_file(self, bucket_path: str, destination_path: str) -> bool:
        """Download file from bucket and save to destination path

        Args:
            bucket_path (str): bucket path to file to download
            destination_path (str): save file to this path

        Returns:
            bool: True if successful, False otherwise
        """
        blob = self.get_blob(bucket_path)
        if blob:
            try:
                blob.download_to_filename(destination_path)
                self.log.info(f'Successfully downloaded object to file {destination_path}')
                return True
            except Exception:
                self.log.exception(f'Failed to download file: {bucket_path}')
        else:
            self.log.error(f'Failed to download file: {bucket_path}')
        return False

    def __get_used_buckets(self) -> list:
        """Get the list of used bucket names

        Returns:
            list: list of used bucket names
        """
        try:
            with open(self.used_buckets_file, 'r') as file:
                return json.load(file)
        except Exception:
            self.log.exception('Failed to get used buckets')
        return []

    def _load_json_service_account(self, sa_path: str) -> dict:
        """Load a service account json file to a dictionary

        Args:
            sa_path (str): path to the service account json file

        Returns:
            dict: service account data
        """
        try:
            with open(sa_path, 'r') as sa_file:
                return json.load(sa_file)
        except Exception:
            self.log.exception('Failed to create credentials file')
        return {}

    def _create_service_account_file(self, sa_file: str, sa_data: dict) -> bool:
        """Create a service account file and encrypt it with the cipher key.

        Args:
            sa_file (str): path to the service account file
            sa_data (dict): service account data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(sa_file, 'wb') as file:
                file.write(self.cipher.encrypt(pickle.dumps(sa_data), self.cipher.load_key()))
            return True
        except Exception:
            self.log.exception('Failed to create service account file')
        return False

    def _add_bucket_to_used_buckets(self, bucket_name: str) -> bool:
        """Add a bucket to the used buckets tracker if not already added

        Args:
            bucket_name (str): the bucket name to add

        Returns:
            bool: True if successful, False otherwise
        """
        used_buckets = self.__get_used_buckets()
        try:
            if bucket_name not in used_buckets:
                used_buckets.append(bucket_name)
                with open(self.used_buckets_file, 'w') as file:
                    json.dump(used_buckets, file)
            return True
        except Exception:
            self.log.exception('Failed to add bucket to used buckets')
        return False

    def get_blob(self, blob_path: str) -> storage.Blob | None:
        """Get blob object from bucket

        Args:
            blob_path (str): bucket path to the blob

        Returns:
            storage.Blob: the blob object or None if failed
        """
        try:
            return self.client.get_bucket(self.bucket).blob(blob_path)
        except Exception:
            self.log.exception('Failed to get blob object')
        return None

    def get_bucket_folder_files(self, folder_path: str):
        """Get all files in a folder in the bucket

        Args:
            folder_path (str): the path to the folder in the bucket

        yield:
            str: the file name in the folder (blob name)
        """
        try:
            for blob in self.client.get_bucket(self.bucket).list_blobs(prefix=folder_path):
                blob: storage.Blob
                yield blob.name
        except Exception:
            self.log.exception('Failed to list files')
        return None

    def get_object_info(self, file_path: str) -> dict:
        """Get the info of a file in the bucket. The info includes the file name, size, checksum and created date

        Args:
            file_path (str): the path to the file in the bucket

        Returns:
            dict: the file info
        """
        blob = self.get_blob(file_path)
        if blob:
            try:
                return {
                    'name': blob.name,
                    'size': blob.size,
                    'checksum': blob.crc32c,
                    'created': blob.time_created,
                }
            except Exception:
                self.log.exception(f'Failed to get file info for: {file_path}')
        else:
            self.log.error(f'File not found: {file_path}')
        return {}

    def download_object_to_file(self, bucket_path: str, destination_path: str, passwd: bool = False) -> bool:
        """Download file from bucket and save to destination path. If passwd is True, password input prompt is provided
        to decrypt the data before saving to file.

        Args:
            bucket_path (str): bucket path to file to download
            destination_path (str): save file to this path
            passwd (bool, optional): option to provide password for decrypt. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if passwd:
            data = self.download_object(bucket_path, passwd)
            try:
                with open(destination_path, 'w') as file:
                    file.write(data)
                self.log.info(f'Successfully downloaded object to file {destination_path}')
                return True
            except Exception:
                self.log.exception('Failed to save file')
                return False
        return self.__download_object_to_file(bucket_path, destination_path)

    def download_object(self, bucket_path: str, passwd: bool = False) -> str:
        """Download data from bucket

        Args:
            bucket_path (str): bucket path to file to download
            passwd (bool, optional): option to provide password for decrypt. Defaults to False.

        Returns:
            str: the downloaded data as string
        """
        blob = self.get_blob(bucket_path)
        if blob:
            try:
                data = blob.download_as_bytes()
                if passwd:
                    return self.cipher.passwd_xor(data, self._prompt_for_passwd(False)).decode()
                return data.decode()
            except UnicodeDecodeError:
                self.log.error('Failed to decrypt data')
            except Exception:
                self.log.exception(f'Failed to download data: {bucket_path}')
        else:
            self.log.error(f'Failed to download data: {bucket_path}')
        return ''

    def delete_bucket_folder(self, folder_path: str, force: bool = False) -> bool:
        """Delete all files in a folder in the bucket. Really, just deletes all files with the prefix provided
        as folders are not a thing in GCP buckets, but we will treat them as such for simplicity.

        Args:
            folder_path (str): the path to the folder in the bucket
            force (bool, optional): force delete. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        self.log.info(f'Deleting files in folder: {folder_path}')
        for blob in self.client.get_bucket(self.bucket).list_blobs(prefix=folder_path):
            blob: storage.Blob
            try:
                if force or input(f'Delete object {blob.name}? (y/n): ').lower() == 'y':
                    blob.delete()
                    self.log.info(f'Deleted file: {blob.name}')
                else:
                    self.log.info(f'Skipped file: {blob.name}')
            except Exception:
                self.log.exception(f'Failed to delete file: {blob.name}')
                return False
        return True

    def delete_object(self, bucket_path: str, force: bool = False) -> bool:
        """Delete file from bucket that matches the provided path

        Args:
            bucket_path (str): the path to the file in the bucket
            force (bool, optional): force delete. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        if bucket_path.endswith('/'):
            return self.delete_bucket_folder(bucket_path, force)
        blob = self.get_blob(bucket_path)
        if blob:
            try:
                if blob.exists():
                    if force or input(f'Delete object {blob.name}? (y/n): ').lower() == 'y':
                        blob.delete()
                        self.log.info(f'Successfully deleted object {bucket_path}')
                        return True
                    else:
                        self.log.info(f'Skipped file: {blob.name}')
                else:
                    self.log.info(f'File not found: {bucket_path}')
                    return True
            except NotFound as error:
                if error.code == 404:
                    self.log.error(f'File not found: {bucket_path}')
            except Exception:
                self.log.exception('Failed to delete file')
        return False

    def display_bucket_folder_files(self, folder_path: str = '') -> bool:
        """Display all files in a folder in the bucket

        Args:
            folder_path (str, optional): object prefix path. Defaults to '' and will use root path.

        Returns:
            bool: True if successful, False otherwise
        """
        payload = 'Contents:\n'
        try:
            for blob_name in self.get_bucket_folder_files(folder_path):
                payload += f'  {blob_name}\n'
            self.display_success(payload.strip())
            return True
        except Exception:
            self.log.exception('Failed to get files')
        return False

    def display_object_info(self, object_name: str) -> bool:
        """Display the info of a file in the bucket. Some items may not be populated in GCP.

        Args:
            object_name (str): the path to the file in the bucket

        Returns:
            bool: True if successful, False otherwise
        """
        info = self.get_object_info(object_name)
        if info:
            return self.display_success(f'Object Info:\n{json.dumps(info, indent=2)}')
        return self.display_error(f'Failed to get object info: {object_name}')

    def display_downloaded_object(self, object_name: str, passwd: bool = False) -> bool:
        """Display the downloaded data from the bucket to console

        Args:
            object_name (str): the path to the file in the bucket
            passwd (bool, optional): option to provide password for decrypt. Defaults to False.

        Returns:
            bool: True if successful, False otherwise
        """
        data = self.download_object(object_name, passwd)
        if data:
            self.display_success(f'Downloaded data:\n{data}')
            return True
        self.display_error(f'Failed to download data: {object_name}')
        return False

    def get_service_accounts(self) -> list:
        """Get a list of service accounts

        Returns:
            list: list of service accounts
        """
        accounts = []
        for file in Path(f'{Path(__file__).parent}/k2g_env/keys/').glob('*.sa'):
            accounts.append(file.name.split('.')[1])
        return accounts

    def list_service_accounts(self) -> bool:
        """List all service accounts

        Returns:
            bool: True if successful, False otherwise
        """
        payload = 'Service accounts:\n'
        default = self.__get_default_service_account()
        for sa in self.get_service_accounts():
            payload += '  ' + sa + ' (default)\n' if sa == default else '  ' + sa + '\n'
        return self.display_success(payload.strip())

    def set_default_service_account(self, default: str) -> bool:
        """Set the default service account

        Args:
            default (str): service account name

        Returns:
            bool: True if successful, False otherwise
        """
        if default in self.get_service_accounts():
            try:
                with open(self.default_sa, 'w') as file:
                    file.write(default)
                self.display_success(f'Set default service account to {default}')
                return self.list_service_accounts()
            except Exception:
                self.log.exception(f'Failed to set default service account to {default}')
        else:
            self.log.error(f'Service account {default} not found')
        return False

    def remove_service_account(self, service_account: str) -> bool:
        """Remove a service account. Cannot remove the default service account.

        Args:
            service_account (str): service account name

        Returns:
            bool: True if successful, False otherwise
        """
        if self.__get_default_service_account() == service_account:
            self.log.error('Cannot remove default service account')
            return False
        if service_account in self.get_service_accounts():
            try:
                remove(f'{Path(__file__).parent}/k2g_env/keys/.{service_account}.sa')
                self.display_success(f'Removed service account {service_account}')
                return self.list_service_accounts()
            except Exception:
                self.log.exception(f'Failed to remove service account {service_account}')
        else:
            self.log.error(f'Service account {service_account} not found')
        return False

    def add_service_account(self, sa_path: str) -> bool:
        """Add a service account

        Args:
            sa_path (str): path to the service account json file

        Returns:
            bool: True if successful, False otherwise
        """
        path = Path(sa_path)
        if path.exists():
            sa = self._load_json_service_account(path)
            if sa:
                name = sa.get('client_email', '').split('@')[0]
                if self._create_service_account_file(f'{Path(__file__).parent}/k2g_env/keys/.{name}.sa', sa):
                    self.display_success(f'Added service account {name}')
                    return self.list_service_accounts()
        else:
            self.log.error(f'File not found: {sa_path}')
        return False

    def list_used_buckets(self) -> bool:
        """List all used bucket names

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = 'Used Buckets:\n'
            default_bucket = self.__get_default_bucket()
            for bucket in self.__get_used_buckets():
                if bucket == default_bucket:
                    payload += f'  {bucket} (default)\n'
                else:
                    payload += f'  {bucket}\n'
            return self.display_success(payload.strip())
        except Exception:
            self.log.exception('Failed to list used buckets')
        return False

    def set_default_bucket(self, default: str) -> bool:
        """Set the default bucket

        Args:
            default (str): bucket name

        Returns:
            bool: True if successful, False otherwise
        """
        self._add_bucket_to_used_buckets(default)
        try:
            with open(self.default_bucket, 'w') as file:
                file.write(default)
            self.display_success(f'Set default bucket to {default}')
            return self.list_used_buckets()
        except Exception:
            self.log.exception(f'Failed to set default bucket to {default}')
        return False

    def remove_used_bucket(self, bucket_name: str) -> bool:
        """Remove a bucket from the used bucket tracker

        Args:
            bucket_name (str): bucket name to remove

        Returns:
            bool: True if successful, False otherwise
        """
        if bucket_name == self.__get_default_bucket():
            return self.display_error('Cannot remove default bucket')
        used_buckets = self.__get_used_buckets()
        if bucket_name in used_buckets:
            used_buckets.remove(bucket_name)
            try:
                with open(self.used_buckets_file, 'w') as file:
                    json.dump(used_buckets, file)
                self.display_success(f'Removed bucket {bucket_name}')
                return self.list_used_buckets()
            except Exception:
                self.log.exception(f'Failed to remove bucket {bucket_name}')
        else:
            self.display_error(f'Bucket {bucket_name} not found')
        return False

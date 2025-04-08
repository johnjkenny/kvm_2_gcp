import json
from logging import Logger

from google.cloud import storage
from google.api_core.exceptions import NotFound

from kvm_2_gcp.utils import Utils


class GCPCloudStorage(Utils):
    def __init__(self, bucket: str = 'default', service_account: str = 'default', set_used_bucket: bool = True,
                 logger: Logger = None):
        """GCP Cloud Storage manager

        Args:
            bucket (str, optional): bucket name to use. Defaults to 'default' and will pull the default bucket name.
            service_account (str, optional): service account to use. Defaults to 'default' and will pull default SA.
            set_used_bucket (bool, optional): option to add bucket to used bucket tracker. Defaults to True.
            logger (Logger, optional): logger object. Defaults to None.
        """
        super().__init__(service_account, logger=logger)
        self.__bucket = bucket
        self.__client: storage.Client | None = None
        if set_used_bucket and bucket != 'default':
            self._add_bucket_to_used_buckets(bucket)

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
            self.display_success_msg(payload.strip())
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
            return self.display_success_msg(f'Object Info:\n{json.dumps(info, indent=2)}')
        return self.display_fail_msg(f'Failed to get object info: {object_name}')

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
            self.display_success_msg(f'Downloaded data:\n{data}')
            return True
        self.display_fail_msg(f'Failed to download data: {object_name}')
        return False

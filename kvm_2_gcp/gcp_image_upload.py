from logging import Logger
from pathlib import Path
from time import sleep
from datetime import datetime

from google.cloud.devtools import cloudbuild_v1
from google.api_core.exceptions import NotFound, PermissionDenied
from google.api_core.operation import Operation

from kvm_2_gcp.utils import Utils
from kvm_2_gcp.cloud_storage import GCPCloudStorage


class GCPImageUpload(Utils):
    def __init__(self, image_name: str, name: str, family: str, bucket: str = 'default',
                 service_account: str = 'default', project_id: str = 'default', logger: Logger = None):
        """Upload KVM image to GCP using Cloud Build and bucket storage

        Args:
            image_name (str): the name of the image to upload
            name (str): name to call the image in GCP
            family (str): family to assign the image to
            bucket (str, optional): bucket to use to store the image upload. Defaults to 'default'.
            service_account (str, optional): service account to use for cloud storage and build. Defaults to 'default'.
            project_id (str, optional): project ID to store the image in. Defaults to 'default'.
            logger (Logger, optional): logger to use. Defaults to None.
        """
        super().__init__(logger=logger)
        self.project_id = project_id if project_id != 'default' else self._load_default_project_id()
        self.__image_name = image_name
        self.__name = name if name != 'default' else Path(self.__image_name).with_suffix('').name
        self.__name = self.__name.replace('.', '-').replace(' ', '-')
        self.__family = family
        self.__bucket_image = f'k2g-images/{self.__image_name}'
        self.__storage = GCPCloudStorage(bucket, service_account, logger=self.log)
        self.__scratch_dir = f'k2g-tmp/{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'

    @property
    def __import_step(self) -> dict:
        """Cloud build import step

        Returns:
            dict: cloud build step to import the image
        """
        return {
            "name": "gcr.io/compute-image-tools/gce_vm_image_import",
            "args": [
                f"-image_name={self.__name}",
                f"-source_file=gs://{self.__storage.bucket}/{self.__bucket_image}",
                f'-scratch_bucket_gcs_path=gs://{self.__storage.bucket}/{self.__scratch_dir}'
            ]
        }

    @property
    def __set_family_step(self) -> dict:
        """Cloud build step to set the image family

        Returns:
            dict: cloud build step to set the image family
        """
        return {
            "name": "gcr.io/cloud-builders/gcloud",
            "args": [
                "compute",
                "images",
                "update",
                self.__name,
                f"--family={self.__family}",
                f"--project={self.project_id}"
            ]
        }

    def __upload_file_to_bucket(self) -> bool:
        """Upload the image to the GCP bucket

        Returns:
            bool: True if upload was successful, False otherwise
        """
        self.log.info(f'Uploading {self.__image_name} to GCP bucket')
        src = Path(f'{self.image_dir}/{self.__image_name}')
        return self.__storage.upload_from_file(src, self.__bucket_image, 'application/x-qemu-disk')

    def __poll_build_state(self, client: cloudbuild_v1.CloudBuildClient, operation: Operation) -> bool:
        """Poll the build state until it is completed or failed

        Args:
            client (cloudbuild_v1.CloudBuildClient): cloud build client
            operation (Operation): operation to poll

        Returns:
            bool: True if the build was successful, False otherwise
        """
        build_id = operation.metadata.build.id
        while True:
            try:
                build = client.get_build(project_id=self.project_id, id=build_id)
                if build.status == cloudbuild_v1.Build.Status.SUCCESS:
                    self.log.info(f"Image import build completed successfully: {build_id}")
                    return True
                elif build.status in [cloudbuild_v1.Build.Status.FAILURE,
                                      cloudbuild_v1.Build.Status.INTERNAL_ERROR,
                                      cloudbuild_v1.Build.Status.TIMEOUT,
                                      cloudbuild_v1.Build.Status.CANCELLED]:
                    self.log.error(f'Image import build {build_id} failed with state: {build.status.name}')
                    return False
                else:
                    self.display_info_msg(f"Build {build_id} is running...")
            except NotFound:
                self.log.error(f"Build not found: {build_id}")
                return False
            sleep(30)

    def __start_image_import_build(self) -> bool:
        """Start the image import build using Cloud Build

        Returns:
            bool: True if the build was successful, False otherwise
        """
        client = cloudbuild_v1.CloudBuildClient(credentials=self.creds)
        build = {'steps': [self.__import_step, self.__set_family_step], 'timeout': {'seconds': 1800}}
        try:
            operation = client.create_build(project_id=self.project_id, build=build)
            self.log.info(f'Image import build started: {operation.metadata.build.id}')
        except PermissionDenied as error:
            self.log.error(f'Permission denied to create build: {error.message}')
            return False
        except Exception:
            self.log.exception('Failed to start image import build')
            return False
        return self.__poll_build_state(client, operation)

    def __cleanup_bucket(self) -> bool:
        """Cleanup the bucket by deleting the image and scratch directory

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        for obj in [self.__bucket_image, self.__scratch_dir + '/']:
            if not self.__storage.delete_object(obj, True):
                return False
        return True

    def upload_image(self) -> bool:
        """Upload the image to GCP by uploading the image to the bucket then using cloud build to build the image.
        Will delete the bucket data after the build is complete.

        Returns:
            bool: True if upload, build, and cleanup was successful else False
        """
        if self.__upload_file_to_bucket() and self.__start_image_import_build():
            return self.__cleanup_bucket()
        return False

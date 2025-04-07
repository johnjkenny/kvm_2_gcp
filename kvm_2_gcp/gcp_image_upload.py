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
        super().__init__(logger=logger)
        self.project_id = project_id if project_id != 'default' else self._load_default_project_id()
        self.__image_name = image_name
        self.__name = name if name != 'default' else Path(self.__image_name).with_suffix('')
        self.__family = family
        self.__bucket_image = f'k2g-images/{self.__image_name}'
        self.__storage = GCPCloudStorage(bucket, service_account, logger=self.log)
        self.__scratch_dir = f'k2g-tmp/{datetime.now().strftime("%Y-%m-%d--%H-%M-%S")}'

    @property
    def __import_step(self):
        return {
            "name": "gcr.io/compute-image-tools/gce_vm_image_import",
            "args": [
                f"-image_name={self.__name}",
                f"-source_file=gs://{self.__storage.bucket}/{self.__bucket_image}",
                f'-scratch_bucket_gcs_path=gs://{self.__storage.bucket}/{self.__scratch_dir}'
            ]
        }

    @property
    def __set_family_step(self):
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

    def __upload_file_to_bucket(self):
        self.log.info(f'Uploading {self.__image_name} to GCP bucket')
        src = Path(f'{self.image_dir}/{self.__image_name}')
        return self.__storage.upload_from_file(src, self.__bucket_image, 'application/x-qemu-disk')

    def __poll_build_state(self, client: cloudbuild_v1.CloudBuildClient, operation: Operation):
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

    def __start_image_import_build(self):
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

    def __cleanup_bucket(self):
        for obj in [self.__bucket_image, self.__scratch_dir + '/']:
            if not self.__storage.delete_object(obj, True):
                return False
        return True

    def upload_image(self):
        state = self.__upload_file_to_bucket() and self.__start_image_import_build()
        self.__cleanup_bucket()
        return state

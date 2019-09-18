from ignition.service.framework import Capability, Service, interface
from ignition.service.config import ConfigurationPropertiesGroup
from ignition.service.api import BaseController
from ignition.model.lifecycle import LifecycleExecution, lifecycle_execution_dict, STATUS_COMPLETE, STATUS_FAILED
from ignition.service.messaging import Message, Envelope, JsonContent
from ignition.utils.file import DirectoryTree
import uuid
import logging
import os
import zipfile
import shutil
import base64
import pathlib
import ignition.openapi as openapi

logger = logging.getLogger(__name__)
# Grabs the __init__.py from the openapi package then takes it's parent, the openapi directory itself
openapi_path = str(pathlib.Path(openapi.__file__).parent.resolve())


class LifecycleProperties(ConfigurationPropertiesGroup, Service, Capability):

    def __init__(self):
        super().__init__('lifecycle')
        self.api_spec = os.path.join(openapi_path, 'vnfc_lifecycle.yaml')
        self.async_messaging_enabled = True
        self.scripts_workspace = './scripts_workspace'


class LifecycleDriverCapability(Capability):

    @interface
    def execute_lifecycle(self, lifecycle_name, lifecycle_scripts_tree, system_properties, properties, deployment_location):
        pass

    @interface
    def get_lifecycle_execution(self, request_id, deployment_location):
        pass


class LifecycleApiCapability(Capability):

    @interface
    def execute(self, **kwarg):
        pass


class LifecycleServiceCapability(Capability):

    @interface
    def execute_lifecycle(self, lifecycle_name, lifecycle_scripts, system_properties, properties, deployment_location):
        pass


class LifecycleScriptFileManagerCapability(Capability):

    @interface
    def build_tree(self, tree_name, lifecycle_scripts):
        pass


class LifecycleExecutionMonitoringCapability(Capability):

    @interface
    def monitor_execution(self, request_id, deployment_location):
        pass


class LifecycleMessagingCapability(Capability):

    @interface
    def send_lifecycle_execution(self, execution_task):
        pass


class LifecycleApiService(Service, LifecycleApiCapability, BaseController):
    """
    Out-of-the-box controller for the Lifecycle API
    """

    def __init__(self, **kwargs):
        if 'service' not in kwargs:
            raise ValueError('No service instance provided')
        self.service = kwargs.get('service')

    def execute(self, **kwarg):
        body = self.get_body(kwarg)
        logger.debug('Handling lifecycle execution request with body %s', body)
        lifecycle_name = self.get_body_required_field(body, 'lifecycleName')
        lifecycle_scripts = self.get_body_required_field(body, 'lifecycleScripts')
        system_properties = self.get_body_required_field(body, 'systemProperties')
        properties = self.get_body_field(body, 'properties', {})
        deployment_location = self.get_body_required_field(body, 'deploymentLocation')
        execute_response = self.service.execute_lifecycle(lifecycle_name, lifecycle_scripts, system_properties, properties, deployment_location)
        response = {'requestId': execute_response.request_id}
        return (response, 202)


class LifecycleService(Service, LifecycleServiceCapability):
    """
    Out-of-the-box service for the Lifecycle API
    """

    def __init__(self, **kwargs):
        if 'driver' not in kwargs:
            raise ValueError('driver argument not provided')
        if 'lifecycle_config' not in kwargs:
            raise ValueError('lifecycle_config argument not provided')
        if 'script_file_manager' not in kwargs:
            raise ValueError('script_file_manager argument not provided')
        self.driver = kwargs.get('driver')
        self.script_file_manager = kwargs.get('script_file_manager')
        lifecycle_config = kwargs.get('lifecycle_config')
        self.async_enabled = lifecycle_config.async_messaging_enabled
        if self.async_enabled is True:
            if 'lifecycle_monitor_service' not in kwargs:
                raise ValueError('lifecycle_monitor_service argument not provided (required when async_messaging_enabled is True)')
            self.lifecycle_monitor_service = kwargs.get('lifecycle_monitor_service')

    def execute_lifecycle(self, lifecycle_name, lifecycle_scripts, system_properties, properties, deployment_location):
        file_name = '{0}'.format(str(uuid.uuid4()))
        lifecycle_scripts_tree = self.script_file_manager.build_tree(file_name, lifecycle_scripts)
        execute_response = self.driver.execute_lifecycle(lifecycle_name, lifecycle_scripts_tree, system_properties, properties, deployment_location)
        if self.async_enabled is True:
            self.__async_lifecycle_execution_completion(execute_response.request_id, deployment_location)
        return execute_response

    def __async_lifecycle_execution_completion(self, request_id, deployment_location):
        self.lifecycle_monitor_service.monitor_execution(request_id, deployment_location)


LIFECYCLE_EXECUTION_MONITOR_JOB_TYPE = 'LifecycleExecutionMonitoring'


class LifecycleExecutionMonitoringService(Service, LifecycleExecutionMonitoringCapability):

    def __init__(self, **kwargs):
        if 'job_queue_service' not in kwargs:
            raise ValueError('job_queue_service argument not provided')
        if 'lifecycle_messaging_service' not in kwargs:
            raise ValueError('lifecycle_messaging_service argument not provided')
        if 'driver' not in kwargs:
            raise ValueError('driver argument not provided')
        self.job_queue_service = kwargs.get('job_queue_service')
        self.lifecycle_messaging_service = kwargs.get('lifecycle_messaging_service')
        self.driver = kwargs.get('driver')
        self.job_queue_service.register_job_handler(LIFECYCLE_EXECUTION_MONITOR_JOB_TYPE, self.job_handler)

    def job_handler(self, job_definition):
        if 'request_id' not in job_definition or job_definition['request_id'] is None:
            logger.warning('Job with {0} job type is missing request_id. This job has been discarded'.format(LIFECYCLE_EXECUTION_MONITOR_JOB_TYPE))
            return True
        if 'deployment_location' not in job_definition or job_definition['deployment_location'] is None:
            logger.warning('Job with {0} job type is missing deployment_location. This job has been discarded'.format(LIFECYCLE_EXECUTION_MONITOR_JOB_TYPE))
            return True
        request_id = job_definition['request_id']
        deployment_location = job_definition['deployment_location']
        lifecycle_execution_task = self.driver.get_lifecycle_execution(request_id, deployment_location)
        status = lifecycle_execution_task.status
        if status in [STATUS_COMPLETE, STATUS_FAILED]:
            self.lifecycle_messaging_service.send_lifecycle_execution(lifecycle_execution_task)
            return True
        return False

    def __create_job_definition(self, request_id, deployment_location):
        return {
            'job_type': LIFECYCLE_EXECUTION_MONITOR_JOB_TYPE,
            'request_id': request_id,
            'deployment_location': deployment_location
        }

    def monitor_execution(self, request_id, deployment_location):
        if request_id is None:
            raise ValueError('Cannot monitor task when request_id is not given')
        if deployment_location is None:
            raise ValueError('Cannot monitor task when deployment_location is not given')
        self.job_queue_service.queue_job(self.__create_job_definition(request_id, deployment_location))


class LifecycleMessagingService(Service, LifecycleMessagingCapability):

    def __init__(self, **kwargs):
        if 'postal_service' not in kwargs:
            raise ValueError('postal_service argument not provided')
        if 'topics_configuration' not in kwargs:
            raise ValueError('topics_configuration argument not provided')
        self.postal_service = kwargs.get('postal_service')
        topics_configuration = kwargs.get('topics_configuration')
        self.lifecycle_execution_events_topic = topics_configuration.lifecycle_execution_events
        if self.lifecycle_execution_events_topic is None:
            raise ValueError('lifecycle_execution_events topic must be set')

    def send_lifecycle_execution(self, lifecycle_execution):
        if lifecycle_execution is None:
            raise ValueError('lifecycle_execution must be set to send an lifecycle execution event')
        lifecycle_execution_message_content = lifecycle_execution_dict(lifecycle_execution)
        message_str = JsonContent(lifecycle_execution_message_content).get()
        self.postal_service.post(Envelope(self.lifecycle_execution_events_topic, Message(message_str)))


class LifecycleScriptFileManagerService(Service, LifecycleScriptFileManagerCapability):

    def __init__(self, **kwargs):
        if 'lifecycle_config' not in kwargs:
            raise ValueError('lifecycle_config argument not provided')
        lifecycle_config = kwargs.get('lifecycle_config')
        self.scripts_workspace = lifecycle_config.scripts_workspace
        if self.scripts_workspace is None:
            raise ValueError('scripts_workspace directory must be set')

    def build_tree(self, tree_name, lifecycle_scripts):
        self.__clear_existing_files(tree_name)
        package_path = self.__write_scripts_to_disk(tree_name, lifecycle_scripts)
        extracted_path = self.__extract_scripts(tree_name, package_path)
        return DirectoryTree(extracted_path)

    def __clear_existing_files(self, tree_name):
        package_write_path = self.__determine_package_path(tree_name)
        if os.path.exists(package_write_path):
            os.remove(package_write_path)
        extracted_path = self.__determine_extracted_path(tree_name)
        if os.path.exists(extracted_path):
            shutil.rmtree(extracted_path)

    def __determine_package_path(self, tree_name):
        package_write_path = os.path.join(self.scripts_workspace, '{0}.zip'.format(tree_name))
        return package_write_path

    def __determine_extracted_path(self, tree_name):
        extracted_path = os.path.join(self.scripts_workspace, tree_name)
        return extracted_path

    def __write_scripts_to_disk(self, tree_name, lifecycle_scripts):
        package_write_path = self.__determine_package_path(tree_name)
        with open(package_write_path, 'wb') as package_writer:
            package_writer.write(base64.b64decode(lifecycle_scripts))
        return package_write_path

    def __extract_scripts(self, tree_name, package_path):
        if not zipfile.is_zipfile(package_path):
            raise ValueError('lifecycle_scripts should include binary contents of a zip file')
        extracted_path = self.__determine_extracted_path(tree_name)
        with zipfile.ZipFile(package_path, 'r') as package_zip:
            package_zip.extractall(extracted_path)
        return extracted_path
import ignition.model.lifecycle as lifecycle_model
import ignition.model.references as reference_model
from ignition.service.framework import Service
from ignition.service.resourcedriver import ResourceDriverHandlerCapability

class ResourceDriverHandler(Service, ResourceDriverHandlerCapability):

    @interface
    def execute_lifecycle(self, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location):
        """
        Execute a lifecycle transition/operation for a Resource.
        This method should return immediate response of the request being accepted,
        it is expected that the ResourceDriverService will poll get_lifecycle_execution on this driver to determine when the request has completed (or devise your own method).

        :param str lifecycle_name: name of the lifecycle transition/operation to execute
        :param ignition.utils.file.DirectoryTree driver_files: object for navigating the directory intended for this driver from the Resource package. The user should call "remove_all" when the files are no longer needed
        :param ignition.utils.propvaluemap.PropValueMap system_properties: properties generated by LM for this Resource: resourceId, resourceName, requestId, metricKey, resourceManagerId, deploymentLocation, resourceType
        :param ignition.utils.propvaluemap.PropValueMap resource_properties: property values of the Resource
        :param ignition.utils.propvaluemap.PropValueMap request_properties: property values of this request
        :param ignition.model.associated_topology.AssociatedTopology associated_topology: 3rd party resources associated to the Resource, from any previous transition/operation requests
        :param dict deployment_location: the deployment location the Resource is assigned to
        :return: an ignition.model.lifecycle.LifecycleExecuteResponse

        :raises:
            ignition.service.resourcedriver.InvalidDriverFilesError: if the scripts are not valid
            ignition.service.resourcedriver.InvalidRequestError: if the request is invalid e.g. if no script can be found to execute the transition/operation given by lifecycle_name
            ignition.service.resourcedriver.TemporaryResourceDriverError: there is an issue handling this request at this time
            ignition.service.resourcedriver.ResourceDriverError: there was an error handling this request
        """
        print("Executing some Lifecycle")
        request_id = '1'
        return lifecycle_model.LifecycleExecuteResponse(request_id)


    @interface
    def get_lifecycle_execution(self, request_id, deployment_location):
        """
        Retrieve the status of a lifecycle transition/operation request

        :param str request_id: identifier of the request to check
        :param dict deployment_location: the deployment location the Resource is assigned to
        :return: an ignition.model.lifecycle.LifecycleExecution
        
        :raises:
            ignition.service.resourcedriver.RequestNotFoundError: if no request with the given request_id exists
            ignition.service.resourcedriver.TemporaryResourceDriverError: there is an issue handling this request at this time, an attempt should be made again at a later time
            ignition.service.resourcedriver.ResourceDriverError: there was an error handling this request
        """
        print("Querying some Lifecycle Execution")
        request_id = '1'
        return lifecycle_model.LifecycleExecution(request_id, lifecycle_model.STATUS_IN_PROGRESS)

    @interface 
    def find_reference(self, instance_name, driver_files, deployment_location):
        """
        Find a Resource, returning the necessary property output values and internal resources from those instances

        :param str instance_name: name used to filter the Resource to find
        :param ignition.utils.file.DirectoryTree driver_files: object for navigating the directory intended for this driver from the Resource package. The user should call "remove_all" when the files are no longer needed
        :param dict deployment_location: the deployment location to find the instance in
        :return: an ignition.model.references.FindReferenceResponse

        :raises:
            ignition.service.resourcedriver.InvalidDriverFilesError: if the scripts are not valid
            ignition.service.resourcedriver.InvalidRequestError: if the request is invalid e.g. if no script can be found to execute the transition/operation given by lifecycle_name
            ignition.service.resourcedriver.TemporaryResourceDriverError: there is an issue handling this request at this time
            ignition.service.resourcedriver.ResourceDriverError: there was an error handling this request
        """
        print("Finding a reference")
        return reference_model.FindReferenceResponse()
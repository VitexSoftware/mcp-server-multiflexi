"""MultiFlexi API client wrapper for MCP Server."""

from __future__ import annotations

import datetime
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .config import MultiFleXiConfig

if TYPE_CHECKING:
    from multiflexi_client.configuration import Configuration as MultiFlexiApiConfiguration
    from multiflexi_client.rest import ApiException


logger = logging.getLogger(__name__)


class MultiFleXiClient:
    """Wrapper for MultiFlexi API client with error handling and convenience methods."""

    def __init__(self, config: MultiFleXiConfig):
        """Initialize the MultiFlexi client with configuration."""
        self.config = config
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging based on configuration."""
        if self.config.debug:
            logging.getLogger("multiflexi_client").setLevel(logging.DEBUG)
            logging.getLogger("urllib3").setLevel(logging.DEBUG)

    def get_configuration(self) -> MultiFlexiApiConfiguration:
        """Get configured MultiFlexi API configuration.

        Imported explicitly from ``multiflexi_client.configuration`` because
        ``multiflexi_client.Configuration`` (top-level re-export) resolves to an
        unrelated domain model (an app "Configuration" record: id/app_id/name/value),
        not the API connection settings class. Using the top-level name here silently
        constructs the wrong object and every API call fails with a pydantic
        ValidationError as soon as ``username``/``password`` are assigned.
        """
        from multiflexi_client.configuration import Configuration as MultiFlexiApiConfiguration

        configuration = MultiFlexiApiConfiguration(host=self.config.host)

        # Configure authentication if credentials are provided
        if self.config.has_auth():
            configuration.username = self.config.username
            configuration.password = self.config.password

        configuration.verify_ssl = self.config.verify_ssl

        return configuration
    
    @contextmanager
    def get_api_client(self):
        """Get configured MultiFlexi API client as context manager.

        Always inject a Basic ``Authorization`` header when credentials are
        configured. Several generated API classes (Credential, CredentialType,
        Topic, Default) ship with empty ``_auth_settings`` because the OpenAPI
        schema omitted ``security: [basicAuth]`` on those operations -- without
        this override those calls go out unauthenticated and the server returns
        Apache's ``401 Basic realm="Protected"``.
        """
        import base64
        import multiflexi_client

        configuration = self.get_configuration()
        with multiflexi_client.ApiClient(configuration) as api_client:
            if self.config.has_auth():
                token = base64.b64encode(
                    f"{self.config.username}:{self.config.password}".encode("utf-8")
                ).decode("ascii")
                api_client.set_default_header("Authorization", f"Basic {token}")
            yield api_client
    
    def format_response(self, response: Any) -> Any:
        """Recursively convert an API response into JSON-serializable data.

        Generated client methods return lists (e.g. ``List[Company]``) and
        plain dicts as often as single model objects. The previous
        implementation only handled the single-object case (``to_dict``) and
        fell back to ``str(response)`` for everything else, which silently
        turned every list/dict response into a Python repr string instead of
        real JSON -- e.g. ``list_companies()`` came back as
        ``{"response": "[Company(id=1, ...), Company(id=2, ...)]"}``.
        """
        if response is None or isinstance(response, (str, int, float, bool)):
            return response
        if isinstance(response, (datetime.datetime, datetime.date)):
            return response.isoformat()
        if isinstance(response, list):
            return [self.format_response(item) for item in response]
        if isinstance(response, dict):
            return {key: self.format_response(value) for key, value in response.items()}
        if hasattr(response, 'to_dict'):
            return self.format_response(response.to_dict())
        if hasattr(response, '__dict__'):
            return self.format_response(response.__dict__)
        return response
    
    def handle_api_error(self, error: ApiException, operation: str) -> Dict[str, Any]:
        """Handle API exceptions and return formatted error response."""
        logger.error(f"API error in {operation}: {error}")
        
        error_data = {
            "error": True,
            "operation": operation,
            "status": getattr(error, 'status', 'unknown'),
            "reason": getattr(error, 'reason', str(error)),
            "body": getattr(error, 'body', None),
        }
        
        # Try to parse error body if available
        if hasattr(error, 'body') and error.body:
            try:
                import json
                error_data["details"] = json.loads(error.body)
            except (json.JSONDecodeError, TypeError):
                error_data["details"] = error.body
        
        return error_data
    
    # Application methods
    def get_apps(self, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get list of applications."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.AppApi(api_client)
                result = api_instance.list_apps(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "get_apps")
    
    def get_app_by_id(self, app_id: int, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get application by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.AppApi(api_client)
                result = api_instance.get_app_by_id(app_id, format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_app_by_id({app_id})")
    
    # Job methods
    def get_jobs(self, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get list of jobs."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.JobApi(api_client)
                result = api_instance.listjobs(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "get_jobs")

    def get_job_by_id(self, job_id: int, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get job by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.JobApi(api_client)
                result = api_instance.getjob_by_id(job_id, format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_job_by_id({job_id})")

    def create_job(
        self,
        runtemplate_id: int,
        scheduled: str = "now",
        executor: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Schedule a job from a RunTemplate (``POST /job/``).

        Mirrors ``multiflexi-cli run-template:schedule``. Requires a
        regenerated ``multiflexi-client`` (>=1.2.0 once released) whose
        ``JobApi.setjob_by_id`` accepts a ``SetjobByIdRequest`` body -- the
        currently-published 1.1.0 has no request-body parameter at all.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.JobApi(api_client)
                request = multiflexi_client.SetjobByIdRequest(
                    runtemplate_id=runtemplate_id,
                    scheduled=scheduled,
                    executor=executor,
                    env=env,
                )
                result = api_instance.setjob_by_id(request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "create_job")

    def get_job_status(self, job_id: int) -> Dict[str, Any]:
        """Get job status by ID.

        multiflexi-client 1.1.0 has no per-job status endpoint -- the only
        ``*_status`` call (``DefaultApi.get_jobs_status``) returns aggregate stats
        across all jobs, not one job's state. Status for a single job is derived
        here from its ``begin``/``end``/``exitcode`` fields instead.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.JobApi(api_client)
                job = api_instance.getjob_by_id(job_id, "json")
                job_dict = self.format_response(job)
                return {
                    "job_id": job_dict.get("id", job_id),
                    "status": self._derive_job_status(job_dict),
                    "begin": job_dict.get("begin"),
                    "end": job_dict.get("end"),
                    "exitcode": job_dict.get("exitcode"),
                }
        except ApiException as e:
            return self.handle_api_error(e, f"get_job_status({job_id})")

    @staticmethod
    def _derive_job_status(job_dict: Dict[str, Any]) -> str:
        """Derive a coarse status label from a Job's begin/end/exitcode fields."""
        if not job_dict.get("begin"):
            return "scheduled"
        if not job_dict.get("end"):
            return "running"
        exitcode = job_dict.get("exitcode")
        return "success" if exitcode == 0 else "failed"
    
    # Company methods
    def get_companies(self, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get list of companies."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CompanyApi(api_client)
                result = api_instance.list_companies(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "get_companies")
    
    def get_company_by_id(self, company_id: int, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get company by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CompanyApi(api_client)
                result = api_instance.get_company_by_id(company_id, format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_company_by_id({company_id})")
    
    # User methods
    def get_users(self, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get list of users."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserApi(api_client)
                result = api_instance.list_users(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "get_users")
    
    def get_user_by_id(self, user_id: int, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get user by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserApi(api_client)
                result = api_instance.get_user_by_id(user_id, format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_user_by_id({user_id})")
    
    # Run Template methods
    def get_runtemplates(self, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get list of run templates."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.RuntemplateApi(api_client)
                result = api_instance.list_run_templates(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "get_runtemplates")

    def get_runtemplate_by_id(self, template_id: int, format_type: str = "json", limit: Optional[int] = None) -> Dict[str, Any]:
        """Get run template by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.RuntemplateApi(api_client)
                result = api_instance.get_run_template_by_id(template_id, format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_runtemplate_by_id({template_id})")

    def update_runtemplate(self, template_id: int, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update run template by ID.

        Note: ``UpdateRunTemplateByIdRequest`` (multiflexi-client 1.1.0) only has
        fields ``id, active, interv, name, delay, executor, cron, note`` -- it has
        no ``description``/``command``/``environment`` fields. Any such keys passed
        in ``template_data`` are silently ignored by pydantic model construction
        (the model's default ``extra="ignore"``), not rejected.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.RuntemplateApi(api_client)
                update_request = multiflexi_client.UpdateRunTemplateByIdRequest(**template_data)
                result = api_instance.update_run_template_by_id(template_id, "json", update_request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"update_runtemplate({template_id})")

    # Company listing / membership methods
    def list_companies(
        self,
        format_type: str = "json",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None,
    ) -> Any:
        """List all companies."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CompanyApi(api_client)
                result = api_instance.list_companies(format_type, limit=limit, offset=offset, order=order)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_companies")

    def list_company_users(
        self,
        company_id: int,
        format_type: str = "json",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None,
    ) -> Any:
        """List users assigned to a company."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserCompanyApi(api_client)
                result = api_instance.list_company_users(
                    company_id, format_type, limit=limit, offset=offset, order=order
                )
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"list_company_users({company_id})")

    def assign_user_to_company(self, company_id: int, user_id: int, role: str = "viewer") -> Any:
        """Assign a user to a company with a given access role."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserCompanyApi(api_client)
                request = multiflexi_client.AssignUserToCompanyRequest(user_id=user_id, role=role)
                result = api_instance.assign_user_to_company(company_id, request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"assign_user_to_company({company_id}, {user_id})")

    def unassign_user_from_company(self, company_id: int, user_id: int) -> Any:
        """Remove a user's assignment from a company."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserCompanyApi(api_client)
                result = api_instance.unassign_user_from_company(company_id, user_id)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"unassign_user_from_company({company_id}, {user_id})")

    # User listing / role methods
    def list_users(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all users."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserApi(api_client)
                result = api_instance.list_users(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_users")

    def get_user_roles(self, user_id: int, format_type: str = "json") -> Any:
        """Get the RBAC roles assigned to a user."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserRoleApi(api_client)
                result = api_instance.get_user_roles(user_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_user_roles({user_id})")

    def set_user_roles(self, user_id: int, roles: List[str], replace: bool = True) -> Any:
        """Assign RBAC roles to a user.

        ``replace=True`` (the API default) removes any existing roles not in
        ``roles``; set ``replace=False`` to add roles without revoking others.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.UserRoleApi(api_client)
                request = multiflexi_client.SetUserRolesRequest(roles=roles)
                result = api_instance.set_user_roles(user_id, request, replace=replace)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"set_user_roles({user_id})")

    # Credential methods
    def list_credentials(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all credentials visible to the authenticated user."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialApi(api_client)
                result = api_instance.get_all_user_credentials(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_credentials")

    def get_credential(self, credential_id: int, format_type: str = "json", token: str = "") -> Any:
        """Get a credential by ID.

        Note: the schema's ``GET /credential/{id}`` declares a required
        ``token`` path/query parameter alongside ``credentialId`` -- this
        looks like a schema-authoring artifact (a stray auth parameter on a
        session-authenticated endpoint) rather than an intentional second
        credential. Passed through as-is; empty string works against the
        current server implementation.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialApi(api_client)
                result = api_instance.get_credential(token, credential_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_credential({credential_id})")

    def update_credential(self, credential_id: int, credential_data: Dict[str, Any], token: str = "") -> Any:
        """Update a credential by ID.

        ``credential_data`` may include ``name``, ``company_id``, ``type``, ``value``.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialApi(api_client)
                update_request = multiflexi_client.UpdateCredentialsRequest(**credential_data)
                result = api_instance.update_credentials(token, credential_id, "json", update_request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"update_credential({credential_id})")

    # CredentialType methods
    def list_credential_types(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all credential types."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialTypeApi(api_client)
                result = api_instance.get_all_credential_types(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_credential_types")

    def get_credential_type(self, credential_type_id: int, format_type: str = "json") -> Any:
        """Get a credential type by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialTypeApi(api_client)
                result = api_instance.get_credential_type(credential_type_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_credential_type({credential_type_id})")

    def update_credential_type(self, credential_type_id: int, credential_type_data: Dict[str, Any]) -> Any:
        """Update a credential type by ID.

        ``credential_type_data`` may include ``name``, ``description``, ``url``, ``logo``.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.CredentialTypeApi(api_client)
                update_request = multiflexi_client.UpdateCredentialTypeRequest(**credential_type_data)
                result = api_instance.update_credential_type(credential_type_id, "json", update_request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"update_credential_type({credential_type_id})")

    # Topic methods
    def list_topics(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all topics (capability contracts required/provided by apps and credentials)."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.TopicApi(api_client)
                result = api_instance.get_all_topics(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_topics")

    def get_topic(self, topic_id: int, format_type: str = "json") -> Any:
        """Get a topic by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.TopicApi(api_client)
                result = api_instance.get_topic(topic_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_topic({topic_id})")

    def update_topic(self, topic_id: int, topic_data: Dict[str, Any]) -> Any:
        """Update a topic by ID.

        ``topic_data`` may include ``name``, ``color``.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.TopicApi(api_client)
                update_request = multiflexi_client.UpdateTopicRequest(**topic_data)
                result = api_instance.update_topic(topic_id, "json", update_request)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"update_topic({topic_id})")

    # EventSource methods
    def list_event_sources(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all event sources (webhook adapters feeding EventRules)."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventsourceApi(api_client)
                result = api_instance.list_event_sources(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_event_sources")

    def get_event_source(self, event_source_id: int, format_type: str = "json") -> Any:
        """Get an event source by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventsourceApi(api_client)
                result = api_instance.get_event_source_by_id(event_source_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_event_source({event_source_id})")

    def set_event_source(self, event_source_data: Dict[str, Any], event_source_id: Optional[int] = None) -> Any:
        """Create (``event_source_id`` omitted) or update an event source."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventsourceApi(api_client)
                event_source = multiflexi_client.EventSource(**event_source_data)
                result = api_instance.set_event_source_by_id(event_source, event_source_id=event_source_id)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"set_event_source({event_source_id})")

    def delete_event_source(self, event_source_id: int, format_type: str = "json") -> Any:
        """Delete an event source by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventsourceApi(api_client)
                api_instance.delete_event_source_by_id(event_source_id, format_type)
                return {"success": True, "event_source_id": event_source_id}
        except ApiException as e:
            return self.handle_api_error(e, f"delete_event_source({event_source_id})")

    def test_event_source_connection(self, event_source_id: int, format_type: str = "json") -> Any:
        """Live-test connectivity/credentials for an event source."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventsourceApi(api_client)
                result = api_instance.test_event_source_connection(event_source_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"test_event_source_connection({event_source_id})")

    # EventRule methods
    def list_event_rules(self, format_type: str = "json", limit: Optional[int] = None) -> Any:
        """List all event rules (bindings from EventSource changes to RunTemplate triggers)."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventruleApi(api_client)
                result = api_instance.list_event_rules(format_type, limit=limit)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_event_rules")

    def get_event_rule(self, event_rule_id: int, format_type: str = "json") -> Any:
        """Get an event rule by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventruleApi(api_client)
                result = api_instance.get_event_rule_by_id(event_rule_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_event_rule({event_rule_id})")

    def set_event_rule(self, event_rule_data: Dict[str, Any], event_rule_id: Optional[int] = None) -> Any:
        """Create (``event_rule_id`` omitted) or update an event rule."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventruleApi(api_client)
                event_rule = multiflexi_client.EventRule(**event_rule_data)
                result = api_instance.set_event_rule_by_id(event_rule, event_rule_id=event_rule_id)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"set_event_rule({event_rule_id})")

    def delete_event_rule(self, event_rule_id: int, format_type: str = "json") -> Any:
        """Delete an event rule by ID."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.EventruleApi(api_client)
                api_instance.delete_event_rule_by_id(event_rule_id, format_type)
                return {"success": True, "event_rule_id": event_rule_id}
        except ApiException as e:
            return self.handle_api_error(e, f"delete_event_rule({event_rule_id})")

    # Task methods (read-only: Tasks are system-materialized per RunTemplate window, not user-created)
    def list_tasks(
        self,
        format_type: str = "json",
        state: Optional[str] = None,
        runtemplate_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        """List tasks (scheduling-window obligations), optionally filtered by state/runtemplate."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.TaskApi(api_client)
                result = api_instance.list_tasks(
                    format_type, state=state, runtemplate_id=runtemplate_id, limit=limit
                )
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "list_tasks")

    def get_task(self, task_id: int, format_type: str = "json") -> Any:
        """Get a task by ID, including its job attempt history."""
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.TaskApi(api_client)
                result = api_instance.get_task_by_id(task_id, format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, f"get_task({task_id})")

    # GDPR methods
    def request_data_export(self, export_type: str, format_type: str = "json") -> Dict[str, Any]:
        """Request GDPR data export.

        Note: ``GdprApi.request_data_export`` exports all data for the
        authenticated user and has no per-category selection, so ``export_type``
        is accepted for interface compatibility but is not sent to the server.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.GdprApi(api_client)
                result = api_instance.request_data_export(action="export", format=format_type)
                return self.format_response(result)
        except ApiException as e:
            return self.handle_api_error(e, "request_data_export")

    def get_export_status(self, export_id: str) -> Dict[str, Any]:
        """Get data export status.

        Note: multiflexi-client 1.1.0 has no per-ID export status lookup.
        ``GdprApi.request_data_export(action="status")`` returns the authenticated
        user's export history instead; ``export_id`` is echoed back in the result
        for the caller to match against it, but is not sent to the server.
        """
        import multiflexi_client
        from multiflexi_client.rest import ApiException
        try:
            with self.get_api_client() as api_client:
                api_instance = multiflexi_client.GdprApi(api_client)
                result = api_instance.request_data_export(action="status")
                response = self.format_response(result)
                response["requested_export_id"] = export_id
                return response
        except ApiException as e:
            return self.handle_api_error(e, f"get_export_status({export_id})")
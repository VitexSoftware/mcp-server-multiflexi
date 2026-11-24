"""Tests for MultiFlexi MCP Server client."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

import multiflexi_client
from multiflexi_client.rest import ApiException

from multiflexi_mcp_server.config import MultiFleXiConfig
from multiflexi_mcp_server.client import MultiFleXiClient


class TestMultiFleXiClient:
    """Test MultiFleXiClient class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MultiFleXiConfig(
            host="https://test.example.com",
            username="testuser",
            password="testpass"
        )
    
    @pytest.fixture
    def client(self, config):
        """Create test client."""
        return MultiFleXiClient(config)
    
    def test_initialization(self, client, config):
        """Test client initialization."""
        assert client.config == config
    
    def test_get_configuration(self, client):
        """Test API configuration creation."""
        configuration = client.get_configuration()
        
        assert configuration.host == "https://test.example.com"
        assert configuration.username == "testuser"
        assert configuration.password == "testpass"
        assert configuration.verify_ssl is True
    
    def test_get_configuration_no_auth(self):
        """Test API configuration without authentication."""
        config = MultiFleXiConfig(host="https://test.example.com")
        client = MultiFleXiClient(config)
        configuration = client.get_configuration()
        
        assert configuration.host == "https://test.example.com"
        assert not hasattr(configuration, 'username') or configuration.username is None
        assert not hasattr(configuration, 'password') or configuration.password is None
    
    def test_format_response_dict(self, client):
        """Test response formatting with to_dict method."""
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": 1, "name": "test"}
        
        result = client.format_response(mock_response)
        assert result == {"id": 1, "name": "test"}
    
    def test_format_response_dict_attribute(self, client):
        """Test response formatting with __dict__ attribute."""
        mock_response = Mock()
        del mock_response.to_dict  # Remove to_dict method
        mock_response.__dict__ = {"id": 1, "name": "test"}
        
        result = client.format_response(mock_response)
        assert result == {"id": 1, "name": "test"}
    
    def test_format_response_string(self, client):
        """Plain scalars pass through unchanged."""
        assert client.format_response("test response") == "test response"
        assert client.format_response(42) == 42
        assert client.format_response(None) is None

    def test_format_response_list_of_models(self, client):
        """Lists of model objects (e.g. List[Company]) serialize element-wise.

        Regression test: the previous implementation only handled a single
        object with ``to_dict()`` and stringified everything else, so a list
        response came back as ``{"response": "[Company(id=1, ...), ...]"}``
        instead of real JSON.
        """
        item1 = Mock()
        item1.to_dict.return_value = {"id": 1}
        item2 = Mock()
        item2.to_dict.return_value = {"id": 2}

        result = client.format_response([item1, item2])
        assert result == [{"id": 1}, {"id": 2}]

    def test_format_response_plain_dict(self, client):
        """A plain dict response is returned as-is, not stringified."""
        result = client.format_response({"success": True, "id": 5})
        assert result == {"success": True, "id": 5}
    
    def test_handle_api_error(self, client):
        """Test API error handling."""
        error = ApiException(status=404, reason="Not Found")
        error.body = '{"message": "Resource not found"}'
        
        result = client.handle_api_error(error, "test_operation")
        
        assert result["error"] is True
        assert result["operation"] == "test_operation"
        assert result["status"] == 404
        assert result["reason"] == "Not Found"
        assert result["details"] == {"message": "Resource not found"}
    
    def test_handle_api_error_no_body(self, client):
        """Test API error handling without body."""
        error = ApiException(status=500, reason="Server Error")
        
        result = client.handle_api_error(error, "test_operation")
        
        assert result["error"] is True
        assert result["operation"] == "test_operation"
        assert result["status"] == 500
        assert result["reason"] == "Server Error"
        assert result["body"] is None
    
    @patch('multiflexi_client.ApiClient')
    def test_get_apps_success(self, mock_api_client_class, client):
        """Test successful get_apps call."""
        # Setup mocks
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client

        mock_app_api = Mock()
        mock_response = Mock()
        mock_response.to_dict.return_value = {"apps": [{"id": 1, "name": "test"}]}
        mock_app_api.list_apps.return_value = mock_response

        with patch('multiflexi_client.AppApi', return_value=mock_app_api):
            result = client.get_apps()

        assert result == {"apps": [{"id": 1, "name": "test"}]}
        mock_app_api.list_apps.assert_called_once_with("json", limit=None)
    
    @patch('multiflexi_client.ApiClient')
    def test_get_apps_api_error(self, mock_api_client_class, client):
        """Test get_apps with API error."""
        # Setup mocks
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client
        
        mock_app_api = Mock()
        mock_app_api.list_apps.side_effect = ApiException(status=500, reason="Server Error")

        with patch('multiflexi_client.AppApi', return_value=mock_app_api):
            result = client.get_apps()
        
        assert result["error"] is True
        assert result["operation"] == "get_apps"
        assert result["status"] == 500
    
    @patch('multiflexi_client.ApiClient')
    def test_get_app_by_id_success(self, mock_api_client_class, client):
        """Test successful get_app_by_id call."""
        # Setup mocks
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client
        
        mock_app_api = Mock()
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": 1, "name": "test"}
        mock_app_api.get_app_by_id.return_value = mock_response
        
        with patch('multiflexi_client.AppApi', return_value=mock_app_api):
            result = client.get_app_by_id(1)
        
        assert result == {"id": 1, "name": "test"}
        mock_app_api.get_app_by_id.assert_called_once_with(1, "json", limit=None)
    
    @patch('multiflexi_client.ApiClient')
    def test_create_job_success(self, mock_api_client_class, client):
        """create_job schedules a job via JobApi.setjob_by_id with a real
        SetjobByIdRequest body (runtemplate_id/scheduled/executor/env)."""
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client

        mock_job_api = Mock()
        mock_response = Mock()
        mock_response.to_dict.return_value = {"id": 42, "runtemplate_id": 1}
        mock_job_api.setjob_by_id.return_value = mock_response

        with patch('multiflexi_client.JobApi', return_value=mock_job_api):
            result = client.create_job(runtemplate_id=1, scheduled="now", env={"FOO": "bar"})

        assert result == {"id": 42, "runtemplate_id": 1}
        call_args = mock_job_api.setjob_by_id.call_args
        request = call_args.args[0]
        assert request.runtemplate_id == 1
        assert request.scheduled == "now"
        assert request.env == {"FOO": "bar"}

    @patch('multiflexi_client.ApiClient')
    def test_create_job_api_error(self, mock_api_client_class, client):
        """create_job surfaces ApiException via handle_api_error."""
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client

        mock_job_api = Mock()
        mock_job_api.setjob_by_id.side_effect = ApiException(status=404, reason="Not Found")

        with patch('multiflexi_client.JobApi', return_value=mock_job_api):
            result = client.create_job(runtemplate_id=999)

        assert result["error"] is True
        assert result["operation"] == "create_job"
        assert result["status"] == 404

    @patch('multiflexi_client.ApiClient')
    def test_get_job_status_derives_from_job(self, mock_api_client_class, client):
        """get_job_status has no dedicated per-job endpoint on the real API;
        it derives status from the Job's begin/end/exitcode fields."""
        mock_api_client = MagicMock()
        mock_api_client_class.return_value.__enter__.return_value = mock_api_client

        mock_job_api = Mock()
        mock_response = Mock()
        mock_response.to_dict.return_value = {
            "id": 1,
            "begin": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T00:01:00Z",
            "exitcode": 0,
        }
        mock_job_api.getjob_by_id.return_value = mock_response

        with patch('multiflexi_client.JobApi', return_value=mock_job_api):
            result = client.get_job_status(1)

        assert result == {
            "job_id": 1,
            "status": "success",
            "begin": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T00:01:00Z",
            "exitcode": 0,
        }
        mock_job_api.getjob_by_id.assert_called_once_with(1, "json")


class TestMultiFleXiClientNewDomains:
    """Tests for the Company/User/Credential/Topic/EventSource/EventRule/Task
    coverage added on top of the original 9-tool surface."""

    @pytest.fixture
    def config(self):
        return MultiFleXiConfig(host="https://test.example.com", username="testuser", password="testpass")

    @pytest.fixture
    def client(self, config):
        return MultiFleXiClient(config)

    @patch('multiflexi_client.ApiClient')
    def test_list_companies_success(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        item = Mock()
        item.to_dict.return_value = {"id": 1, "name": "Acme"}
        mock_company_api = Mock()
        mock_company_api.list_companies.return_value = [item]

        with patch('multiflexi_client.CompanyApi', return_value=mock_company_api):
            result = client.list_companies()

        assert result == [{"id": 1, "name": "Acme"}]

    @patch('multiflexi_client.ApiClient')
    def test_assign_user_to_company(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_uc_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"user_id": 3, "company_id": 1, "role": "manager"}
        mock_uc_api.assign_user_to_company.return_value = response

        with patch('multiflexi_client.UserCompanyApi', return_value=mock_uc_api):
            result = client.assign_user_to_company(1, 3, "manager")

        assert result == {"user_id": 3, "company_id": 1, "role": "manager"}
        request = mock_uc_api.assign_user_to_company.call_args.args[1]
        assert request.user_id == 3
        assert request.role == "manager"

    @patch('multiflexi_client.ApiClient')
    def test_set_user_roles(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_role_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"user_id": 2, "roles": ["admin"]}
        mock_role_api.set_user_roles.return_value = response

        with patch('multiflexi_client.UserRoleApi', return_value=mock_role_api):
            result = client.set_user_roles(2, ["admin"], replace=False)

        assert result == {"user_id": 2, "roles": ["admin"]}
        args, kwargs = mock_role_api.set_user_roles.call_args
        assert args[0] == 2
        assert args[1].roles == ["admin"]
        assert kwargs["replace"] is False

    @patch('multiflexi_client.ApiClient')
    def test_get_credential(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_cred_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 7, "name": "FioToken"}
        mock_cred_api.get_credential.return_value = response

        with patch('multiflexi_client.CredentialApi', return_value=mock_cred_api):
            result = client.get_credential(7)

        assert result == {"id": 7, "name": "FioToken"}
        mock_cred_api.get_credential.assert_called_once_with("", 7, "json")

    @patch('multiflexi_client.ApiClient')
    def test_update_credential(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_cred_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 7, "name": "Renamed"}
        mock_cred_api.update_credentials.return_value = response

        with patch('multiflexi_client.CredentialApi', return_value=mock_cred_api):
            result = client.update_credential(7, {"name": "Renamed"})

        assert result == {"id": 7, "name": "Renamed"}
        args, _ = mock_cred_api.update_credentials.call_args
        assert args[0] == ""
        assert args[1] == 7
        assert args[3].name == "Renamed"

    @patch('multiflexi_client.ApiClient')
    def test_update_credential_type(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_ct_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 3, "name": "FioBank"}
        mock_ct_api.update_credential_type.return_value = response

        with patch('multiflexi_client.CredentialTypeApi', return_value=mock_ct_api):
            result = client.update_credential_type(3, {"name": "FioBank"})

        assert result == {"id": 3, "name": "FioBank"}
        args, _ = mock_ct_api.update_credential_type.call_args
        assert args[0] == 3
        assert args[2].name == "FioBank"

    @patch('multiflexi_client.ApiClient')
    def test_update_topic(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_topic_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 5, "name": "FioBank", "color": "#123456"}
        mock_topic_api.update_topic.return_value = response

        with patch('multiflexi_client.TopicApi', return_value=mock_topic_api):
            result = client.update_topic(5, {"color": "#123456"})

        assert result == {"id": 5, "name": "FioBank", "color": "#123456"}
        args, _ = mock_topic_api.update_topic.call_args
        assert args[0] == 5
        assert args[2].color == "#123456"

    @patch('multiflexi_client.ApiClient')
    def test_list_topics_api_error(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_topic_api = Mock()
        mock_topic_api.get_all_topics.side_effect = ApiException(status=500, reason="Server Error")

        with patch('multiflexi_client.TopicApi', return_value=mock_topic_api):
            result = client.list_topics()

        assert result["error"] is True
        assert result["operation"] == "list_topics"

    @patch('multiflexi_client.ApiClient')
    def test_set_event_source_create(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_es_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 9, "name": "Webhook"}
        mock_es_api.set_event_source_by_id.return_value = response

        with patch('multiflexi_client.EventsourceApi', return_value=mock_es_api):
            result = client.set_event_source({"name": "Webhook", "adapter_type": "generic"})

        assert result == {"id": 9, "name": "Webhook"}
        call_args, call_kwargs = mock_es_api.set_event_source_by_id.call_args
        assert call_args[0].name == "Webhook"
        assert call_kwargs["event_source_id"] is None

    @patch('multiflexi_client.ApiClient')
    def test_test_event_source_connection(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_es_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"reachable": True}
        mock_es_api.test_event_source_connection.return_value = response

        with patch('multiflexi_client.EventsourceApi', return_value=mock_es_api):
            result = client.test_event_source_connection(9)

        assert result == {"reachable": True}

    @patch('multiflexi_client.ApiClient')
    def test_delete_event_rule(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_er_api = Mock()
        mock_er_api.delete_event_rule_by_id.return_value = None

        with patch('multiflexi_client.EventruleApi', return_value=mock_er_api):
            result = client.delete_event_rule(4)

        assert result == {"success": True, "event_rule_id": 4}

    @patch('multiflexi_client.ApiClient')
    def test_list_jobs_filters_pages_and_strips_large_fields(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        jobs = [
            {"id": i, "runtemplate_id": 34 if i % 2 else 1, "begin": "2026-11-24", "end": "2026-11-24",
             "exitcode": 1 if i % 2 else 0, "env": "secret", "stdout": "x"}
            for i in range(250, 0, -1)
        ]
        api = Mock()
        api.listjobs.side_effect = lambda fmt, limit, offset: {
            str(j["id"]): j for j in jobs[offset:offset + limit]
        }

        with patch('multiflexi_client.JobApi', return_value=api):
            result = client.list_jobs(status="failed", runtemplate_id=34, limit=110)
            everything = client.list_jobs(status="success", limit=500)

        assert [j["id"] for j in result["jobs"]] == list(range(249, 30, -2))
        assert all(j["status"] == "failed" and "env" not in j and "stdout" not in j for j in result["jobs"])
        assert len(everything["jobs"]) == 125 and everything["complete"] is True

    @patch('multiflexi_client.ApiClient')
    def test_list_tasks_with_filters(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_task_api = Mock()
        item = Mock()
        item.to_dict.return_value = {"id": 1, "state": "fulfilled"}
        mock_task_api.list_tasks.return_value = [item]

        with patch('multiflexi_client.TaskApi', return_value=mock_task_api):
            result = client.list_tasks(state="fulfilled", runtemplate_id=5)

        assert result == [{"id": 1, "state": "fulfilled"}]
        mock_task_api.list_tasks.assert_called_once_with("json", state="fulfilled", runtemplate_id=5, limit=None)

    @patch('multiflexi_client.ApiClient')
    def test_get_task(self, mock_api_client_class, client):
        mock_api_client_class.return_value.__enter__.return_value = MagicMock()
        mock_task_api = Mock()
        response = Mock()
        response.to_dict.return_value = {"id": 1, "jobs": []}
        mock_task_api.get_task_by_id.return_value = response

        with patch('multiflexi_client.TaskApi', return_value=mock_task_api):
            result = client.get_task(1)

        assert result == {"id": 1, "jobs": []}
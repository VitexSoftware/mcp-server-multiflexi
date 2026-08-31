"""Tests for MultiFlexi MCP Server main module."""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from mcp_types import TextContent

import inspect

from multiflexi_mcp_server.server import (
    app,
    list_resources,
    read_resource,
    list_tools,
    call_tool,
    list_prompts,
    get_prompt,
    main,
)


def test_main_is_sync_entry_point():
    """The `multiflexi-mcp-server` console script calls main() without awaiting
    it, so main must be a plain sync function (previously it was `async def`,
    which meant the console script printed an unawaited-coroutine
    RuntimeWarning and exited immediately without starting the server)."""
    assert not inspect.iscoroutinefunction(main)


class TestMCPServer:
    """Test MCP Server functionality."""
    
    @pytest.mark.asyncio
    async def test_list_resources(self):
        """Test resource listing."""
        resources = await list_resources()

        assert len(resources) == 11
        resource_uris = [str(r.uri) for r in resources]

        assert "multiflexi://apps" in resource_uris
        assert "multiflexi://jobs" in resource_uris
        assert "multiflexi://companies" in resource_uris
        assert "multiflexi://users" in resource_uris
        assert "multiflexi://runtemplates" in resource_uris
        assert "multiflexi://credentials" in resource_uris
        assert "multiflexi://credential_types" in resource_uris
        assert "multiflexi://topics" in resource_uris
        assert "multiflexi://eventsources" in resource_uris
        assert "multiflexi://eventrules" in resource_uris
        assert "multiflexi://tasks" in resource_uris
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_read_resource_apps_with_anyurl(self, mock_client):
        """The real mcp SDK invokes read_resource() with a pydantic AnyUrl
        instance (despite the `str` type hint), not a plain str. AnyUrl(...) ==
        "multiflexi://apps" is False even though str(AnyUrl(...)) matches, so a
        naive `if uri == "multiflexi://apps"` silently falls through to
        "Resource not found" for every real MCP client -- confirmed via a live
        stdio MCP session against a real server before this was fixed."""
        from pydantic import AnyUrl

        mock_client.get_apps.return_value = {"apps": [{"id": 1, "name": "test"}]}

        result = await read_resource(AnyUrl("multiflexi://apps"))

        assert "Resource not found" not in result
        mock_client.get_apps.assert_called_once()

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_read_resource_apps(self, mock_client):
        """Test reading apps resource."""
        mock_client.get_apps.return_value = {"apps": [{"id": 1, "name": "test"}]}

        result = await read_resource("multiflexi://apps")
        parsed_result = json.loads(result)
        
        assert parsed_result == {"apps": [{"id": 1, "name": "test"}]}
        mock_client.get_apps.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_read_resource_jobs(self, mock_client):
        """Test reading jobs resource."""
        mock_client.get_jobs.return_value = {"jobs": [{"id": 1, "name": "test"}]}
        
        result = await read_resource("multiflexi://jobs")
        parsed_result = json.loads(result)
        
        assert parsed_result == {"jobs": [{"id": 1, "name": "test"}]}
        mock_client.get_jobs.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_resource_unknown(self):
        """Test reading unknown resource."""
        result = await read_resource("multiflexi://unknown")
        assert result == "Resource not found: multiflexi://unknown"
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_read_resource_exception(self, mock_client):
        """Test reading resource with exception."""
        mock_client.get_apps.side_effect = Exception("Test error")
        
        result = await read_resource("multiflexi://apps")
        assert "Unexpected error: Test error" in result
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test tool listing."""
        tools = await list_tools()

        assert len(tools) == 37
        tool_names = [t.name for t in tools]

        expected_tools = [
            "get_app", "get_job", "create_job", "get_job_status",
            "get_company", "get_user", "get_runtemplate", "update_runtemplate",
            "request_data_export", "get_export_status",
            "list_companies", "list_company_users", "assign_user_to_company",
            "unassign_user_from_company", "list_users", "get_user_roles",
            "set_user_roles", "list_credentials", "get_credential", "update_credential",
            "list_credential_types", "get_credential_type", "update_credential_type",
            "list_topics", "get_topic", "update_topic",
            "list_event_sources", "get_event_source",
            "set_event_source", "delete_event_source", "test_event_source_connection",
            "list_event_rules", "get_event_rule", "set_event_rule",
            "delete_event_rule", "list_tasks", "get_task",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_have_boolean_annotations(self):
        """Every tool must declare the four MCP tool-annotation hints as
        actual booleans (required by, e.g., OpenAI's tool directory)."""
        tools = await list_tools()

        for tool in tools:
            assert tool.annotations is not None, f"{tool.name} has no annotations"
            for hint in (
                tool.annotations.read_only_hint,
                tool.annotations.destructive_hint,
                tool.annotations.idempotent_hint,
                tool.annotations.open_world_hint,
            ):
                assert isinstance(hint, bool), f"{tool.name} has a non-boolean hint"

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_get_app(self, mock_client):
        """Test get_app tool call."""
        mock_client.get_app_by_id.return_value = {"id": 1, "name": "test"}
        
        result = await call_tool("get_app", {"app_id": 1, "format": "json"})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"id": 1, "name": "test"}
        
        mock_client.get_app_by_id.assert_called_once_with(1, "json")
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_blocks_mutating_tools_in_read_only_mode(self, mock_client):
        """Mutating tools are rejected before touching the client when read_only is on (the default)."""
        result = await call_tool("create_job", {"runtemplate_id": 5})

        parsed_result = json.loads(result[0].text)
        assert parsed_result["error"] is True
        assert parsed_result["tool"] == "create_job"
        assert "read-only" in parsed_result["message"]
        mock_client.create_job.assert_not_called()

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.config.read_only', False)
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_create_job(self, mock_client):
        """Test create_job tool call."""
        mock_client.create_job.return_value = {"id": 1, "runtemplate_id": 5}

        result = await call_tool("create_job", {
            "runtemplate_id": 5,
            "scheduled": "now",
            "env": {"FOO": "bar"}
        })

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"id": 1, "runtemplate_id": 5}

        mock_client.create_job.assert_called_once_with(
            runtemplate_id=5, scheduled="now", executor=None, env={"FOO": "bar"}
        )
    
    @pytest.mark.asyncio
    async def test_call_tool_unknown(self):
        """Test unknown tool call."""
        result = await call_tool("unknown_tool", {})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result["error"] is True
        assert "Unknown tool: unknown_tool" in parsed_result["message"]
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_exception(self, mock_client):
        """Test tool call with exception."""
        mock_client.get_app_by_id.side_effect = Exception("Test error")
        
        result = await call_tool("get_app", {"app_id": 1})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result["error"] is True
        assert "Test error" in parsed_result["message"]
        assert parsed_result["tool"] == "get_app"
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_get_job_status(self, mock_client):
        """Test get_job_status tool call."""
        mock_client.get_job_status.return_value = {"job_id": 1, "status": "running"}
        
        result = await call_tool("get_job_status", {"job_id": 1})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"job_id": 1, "status": "running"}
        
        mock_client.get_job_status.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.config.read_only', False)
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_request_data_export(self, mock_client):
        """Test request_data_export tool call."""
        mock_client.request_data_export.return_value = {"export_id": "123", "status": "pending"}
        
        result = await call_tool("request_data_export", {
            "export_type": "personal_data",
            "format": "json"
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"export_id": "123", "status": "pending"}
        
        mock_client.request_data_export.assert_called_once_with("personal_data", "json")

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_list_companies(self, mock_client):
        mock_client.list_companies.return_value = [{"id": 1, "name": "Acme"}]

        result = await call_tool("list_companies", {"limit": 10})

        parsed_result = json.loads(result[0].text)
        assert parsed_result == [{"id": 1, "name": "Acme"}]
        mock_client.list_companies.assert_called_once_with(limit=10, offset=None, order=None)

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.config.read_only', False)
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_set_user_roles(self, mock_client):
        mock_client.set_user_roles.return_value = {"user_id": 1, "roles": ["admin"]}

        result = await call_tool("set_user_roles", {"user_id": 1, "roles": ["admin"], "replace": False})

        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"user_id": 1, "roles": ["admin"]}
        mock_client.set_user_roles.assert_called_once_with(1, ["admin"], False)

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.config.read_only', False)
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_set_event_source_strips_id_from_payload(self, mock_client):
        """event_source_id must route to the id kwarg, not leak into the data dict."""
        mock_client.set_event_source.return_value = {"id": 5, "name": "Webhook"}

        result = await call_tool("set_event_source", {"event_source_id": 5, "name": "Webhook"})

        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"id": 5, "name": "Webhook"}
        mock_client.set_event_source.assert_called_once_with({"name": "Webhook"}, event_source_id=5)

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_test_event_source_connection(self, mock_client):
        mock_client.test_event_source_connection.return_value = {"reachable": True}

        result = await call_tool("test_event_source_connection", {"event_source_id": 5})

        parsed_result = json.loads(result[0].text)
        assert parsed_result == {"reachable": True}
        mock_client.test_event_source_connection.assert_called_once_with(5)

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_call_tool_list_tasks(self, mock_client):
        mock_client.list_tasks.return_value = [{"id": 1, "state": "open"}]

        result = await call_tool("list_tasks", {"state": "open"})

        parsed_result = json.loads(result[0].text)
        assert parsed_result == [{"id": 1, "state": "open"}]
        mock_client.list_tasks.assert_called_once_with(state="open", runtemplate_id=None, limit=None)

    @pytest.mark.asyncio
    @patch('multiflexi_mcp_server.server.client')
    async def test_read_resource_tasks(self, mock_client):
        mock_client.list_tasks.return_value = [{"id": 1, "state": "open"}]

        result = await read_resource("multiflexi://tasks")
        parsed_result = json.loads(result)

        assert parsed_result == [{"id": 1, "state": "open"}]

    @pytest.mark.asyncio
    async def test_list_prompts(self):
        prompts = await list_prompts()

        assert len(prompts) == 3
        prompt_names = [p.name for p in prompts]
        assert prompt_names == [
            "diagnose_job_failure",
            "task_fulfillment_report",
            "gdpr_export_checklist",
        ]

    @pytest.mark.asyncio
    async def test_get_prompt_diagnose_job_failure(self):
        result = await get_prompt("diagnose_job_failure", {"job_id": "42"})

        text = result.messages[0].content.text
        assert "job 42" in text
        assert "job_id=42" in text

    @pytest.mark.asyncio
    async def test_get_prompt_task_fulfillment_report_no_filter(self):
        result = await get_prompt("task_fulfillment_report", {})

        text = result.messages[0].content.text
        assert "all RunTemplates" in text
        assert "runtemplate_id=" not in text

    @pytest.mark.asyncio
    async def test_get_prompt_task_fulfillment_report_with_filter(self):
        result = await get_prompt("task_fulfillment_report", {"runtemplate_id": "7"})

        text = result.messages[0].content.text
        assert "RunTemplate 7" in text
        assert "runtemplate_id=7" in text

    @pytest.mark.asyncio
    async def test_get_prompt_gdpr_export_checklist_default(self):
        result = await get_prompt("gdpr_export_checklist", {})

        text = result.messages[0].content.text
        assert "personal_data" in text

    @pytest.mark.asyncio
    async def test_get_prompt_gdpr_export_checklist_custom_type(self):
        result = await get_prompt("gdpr_export_checklist", {"export_type": "financial"})

        text = result.messages[0].content.text
        assert "financial" in text

    @pytest.mark.asyncio
    async def test_get_prompt_unknown(self):
        result = await get_prompt("no_such_prompt", {})

        assert "Unknown prompt" in result.messages[0].content.text
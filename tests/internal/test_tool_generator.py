"""
Tests for MCP tool generator.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from finos_mcp.internal.tool_generator import (
    GeneratedTool,
    ToolGenerator,
    ToolTemplate,
)


class TestToolTemplate:
    """Test tool template configuration."""

    def test_basic_template(self):
        """Test basic template creation."""
        template = ToolTemplate(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )

        assert template.name == "test_tool"
        assert template.description == "A test tool"
        assert "query" in template.input_schema["properties"]


class TestGeneratedTool:
    """Test generated tool structure."""

    def test_generated_tool_creation(self):
        """Test creating a generated tool."""
        tool = GeneratedTool(
            name="example_tool",
            description="Example tool",
            code="# Generated code here",
            test_code="# Test code here",
        )

        assert tool.name == "example_tool"
        assert tool.description == "Example tool"
        assert "Generated code" in tool.code
        assert "Test code" in tool.test_code


class TestToolGenerator:
    """Test tool generator functionality."""

    def test_generator_creation(self):
        """Test creating generator instance."""
        generator = ToolGenerator()
        assert generator is not None

    def test_generate_simple_tool(self):
        """Test generating a simple tool."""
        template = ToolTemplate(
            name="simple_search",
            description="Simple search tool",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        )

        generator = ToolGenerator()
        generated = generator.generate_tool(template)

        assert generated.name == "simple_search"
        assert generated.description == "Simple search tool"
        assert "simple_search" in generated.code
        assert "class SimpleSearchRequest" in generated.code
        assert "test_simple_search" in generated.test_code

    def test_generate_tool_with_multiple_params(self):
        """Test generating tool with multiple parameters."""
        template = ToolTemplate(
            name="advanced_search",
            description="Advanced search with filters",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Search category"},
                    "limit": {
                        "type": "integer",
                        "description": "Result limit",
                        "default": 10,
                    },
                },
                "required": ["query", "category"],
            },
        )

        generator = ToolGenerator()
        generated = generator.generate_tool(template)

        assert "query: str" in generated.code
        assert "category: str" in generated.code
        assert "limit: int = Field(default=10" in generated.code

    def test_generate_with_custom_handler(self):
        """Test generating tool with custom handler logic."""
        template = ToolTemplate(
            name="data_processor",
            description="Process data",
            input_schema={
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "Data to process"}
                },
                "required": ["data"],
            },
            custom_logic="processed_data = arguments['data'].upper()\nreturn processed_data",
        )

        generator = ToolGenerator()
        generated = generator.generate_tool(template)

        assert "processed_data = arguments['data'].upper()" in generated.code

    @pytest.mark.asyncio
    async def test_write_tool_files(self):
        """Test writing generated tool to files."""
        template = ToolTemplate(
            name="test_writer",
            description="Test writing tool",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["content"],
            },
        )

        generator = ToolGenerator()
        generated = generator.generate_tool(template)

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "tools"
            with (
                patch("builtins.open"),
                patch("pathlib.Path.exists", return_value=False),
            ):
                result = await generator.write_tool_files(generated, temp_path)

                assert result["tool_file"] == temp_path / "test_writer.py"
                assert result["test_file"] == temp_path / "test_test_writer.py"

    def test_snake_case_conversion(self):
        """Test converting names to snake case."""
        generator = ToolGenerator()

        assert generator._to_snake_case("SimpleSearch") == "simple_search"
        assert (
            generator._to_snake_case("AdvancedDataProcessor")
            == "advanced_data_processor"
        )
        assert generator._to_snake_case("already_snake_case") == "already_snake_case"

    def test_pascal_case_conversion(self):
        """Test converting names to Pascal case."""
        generator = ToolGenerator()

        assert generator._to_pascal_case("simple_search") == "SimpleSearch"
        assert (
            generator._to_pascal_case("advanced_data_processor")
            == "AdvancedDataProcessor"
        )
        assert generator._to_pascal_case("AlreadyPascal") == "AlreadyPascal"

    def test_validate_template(self):
        """Test template validation."""
        generator = ToolGenerator()

        # Valid template
        valid_template = ToolTemplate(
            name="valid_tool",
            description="Valid tool",
            input_schema={"type": "object", "properties": {}},
        )

        # Should not raise
        generator._validate_template(valid_template)

        # Invalid template - empty name
        invalid_template = ToolTemplate(
            name="", description="Invalid", input_schema={"type": "object"}
        )

        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            generator._validate_template(invalid_template)

    def test_generate_pydantic_model(self):
        """Test generating Pydantic model from schema."""
        generator = ToolGenerator()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer", "description": "User age", "default": 18},
                "active": {
                    "type": "boolean",
                    "description": "Is active",
                    "default": True,
                },
            },
            "required": ["name"],
        }

        model_code = generator._generate_pydantic_model("UserRequest", schema)

        assert "class UserRequest(BaseModel):" in model_code
        assert "name: str = Field" in model_code
        assert "age: int = Field(default=18" in model_code
        assert "active: bool = Field(default=True" in model_code

    def test_generate_tool_definition(self):
        """Test generating MCP tool definition."""
        generator = ToolGenerator()

        template = ToolTemplate(
            name="search_users",
            description="Search for users",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        )

        tool_def = generator._generate_tool_definition(template)

        assert 'name="search_users"' in tool_def
        assert 'description="Search for users"' in tool_def
        assert "'query'" in tool_def

    def test_generate_handler_function(self):
        """Test generating tool handler function."""
        generator = ToolGenerator()

        template = ToolTemplate(
            name="process_data",
            description="Process some data",
            input_schema={
                "type": "object",
                "properties": {
                    "input_data": {"type": "string", "description": "Data to process"}
                },
                "required": ["input_data"],
            },
            custom_logic="result = arguments['input_data'].upper()\nreturn [TextContent(type='text', text=result)]",
        )

        handler = generator._generate_handler_function(template)

        assert "async def handle_process_data_tool" in handler
        assert "ProcessDataRequest(**arguments)" in handler
        assert "result = arguments['input_data'].upper()" in handler

    def test_generate_test_code(self):
        """Test generating test code."""
        generator = ToolGenerator()

        template = ToolTemplate(
            name="example_tool",
            description="Example tool for testing",
            input_schema={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "Input value"}
                },
                "required": ["value"],
            },
        )

        test_code = generator._generate_test_code(template)

        assert "class TestExampleTool:" in test_code
        assert "def test_example_tool_request_validation" in test_code
        assert "@pytest.mark.asyncio" in test_code
        assert "async def test_handle_example_tool_tool" in test_code

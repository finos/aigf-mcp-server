"""
Tests for code quality automation.
Enhanced pre-commit hooks and auto-generation for MCP development.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from finos_mcp.internal.code_quality_automation import (
    AutoGenerator,
    CodeTemplate,
    PreCommitHook,
    QualityGate,
    QualityReport,
)


class TestQualityReport:
    """Test quality report generation."""

    def test_report_creation(self):
        """Test creating quality report."""
        report = QualityReport()
        assert report.passed == 0
        assert report.failed == 0
        assert len(report.issues) == 0
        assert report.overall_score == 100.0

    def test_add_passed_check(self):
        """Test adding passed quality check."""
        report = QualityReport()
        report.add_passed("linting")
        
        assert report.passed == 1
        assert report.failed == 0
        assert report.overall_score == 100.0

    def test_add_failed_check(self):
        """Test adding failed quality check."""
        report = QualityReport()
        report.add_failed("tests", "2 tests failed")
        
        assert report.passed == 0
        assert report.failed == 1
        assert "tests" in report.issues
        assert report.issues["tests"] == "2 tests failed"
        assert report.overall_score == 0.0

    def test_mixed_results_scoring(self):
        """Test quality scoring with mixed results."""
        report = QualityReport()
        report.add_passed("linting")
        report.add_passed("formatting")
        report.add_failed("tests", "1 test failed")
        
        assert report.passed == 2
        assert report.failed == 1
        assert report.overall_score == 66.7  # 2/3 * 100

    def test_report_summary(self):
        """Test generating report summary."""
        report = QualityReport()
        report.add_passed("linting")
        report.add_failed("coverage", "Coverage too low: 65%")
        
        summary = report.get_summary()
        assert "Quality Score: 50.0%" in summary
        assert "✅ linting" in summary
        assert "❌ coverage: Coverage too low: 65%" in summary

    def test_is_passing(self):
        """Test overall pass/fail determination."""
        report = QualityReport()
        assert report.is_passing() is True  # No checks = pass
        
        report.add_passed("linting")
        assert report.is_passing() is True
        
        report.add_failed("tests", "failure")
        assert report.is_passing() is False


class TestQualityGate:
    """Test quality gate enforcement."""

    def test_gate_creation(self):
        """Test creating quality gate."""
        gate = QualityGate(
            min_coverage=80.0,
            require_tests=True,
            max_complexity=10
        )
        
        assert gate.min_coverage == 80.0
        assert gate.require_tests is True
        assert gate.max_complexity == 10

    @pytest.mark.asyncio
    async def test_run_linting_check(self):
        """Test running linting quality check."""
        gate = QualityGate()
        
        # Mock successful linting
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="All checks passed")
            
            report = QualityReport()
            await gate._check_linting(report, [Path("test.py")])
            
            assert report.passed == 1
            assert report.failed == 0

    @pytest.mark.asyncio
    async def test_run_linting_check_failure(self):
        """Test linting check with failures."""
        gate = QualityGate()
        
        # Mock failed linting
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="Linting errors found")
            
            report = QualityReport()
            await gate._check_linting(report, [Path("test.py")])
            
            assert report.passed == 0
            assert report.failed == 1
            assert "linting" in report.issues

    @pytest.mark.asyncio
    async def test_coverage_check(self):
        """Test coverage quality check."""
        gate = QualityGate(min_coverage=80.0)
        
        # Mock coverage output
        coverage_output = """
        Name                     Stmts   Miss  Cover
        --------------------------------------------
        src/module.py              100     10    90%
        --------------------------------------------
        TOTAL                      100     10    90%
        """
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=coverage_output)
            
            report = QualityReport()
            await gate._check_coverage(report)
            
            assert report.passed == 1  # 90% > 80%
            assert report.failed == 0

    @pytest.mark.asyncio
    async def test_coverage_check_too_low(self):
        """Test coverage check with insufficient coverage."""
        gate = QualityGate(min_coverage=80.0)
        
        coverage_output = """
        TOTAL                      100     30    70%
        """
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=coverage_output)
            
            report = QualityReport()
            await gate._check_coverage(report)
            
            assert report.passed == 0
            assert report.failed == 1
            assert "Coverage too low: 70.0%" in report.issues["coverage"]

    @pytest.mark.asyncio
    async def test_test_execution_check(self):
        """Test running test execution check."""
        gate = QualityGate(require_tests=True)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="5 passed")
            
            report = QualityReport()
            await gate._check_tests(report, [Path("test_*.py")])
            
            assert report.passed == 1
            assert report.failed == 0

    @pytest.mark.asyncio
    async def test_full_quality_check(self):
        """Test running all quality checks."""
        gate = QualityGate(min_coverage=70.0, require_tests=True)
        
        with patch.object(gate, "_check_linting") as mock_lint, \
             patch.object(gate, "_check_coverage") as mock_cov, \
             patch.object(gate, "_check_tests") as mock_test:
            
            # All checks pass
            async def pass_check(report, *args):
                report.add_passed("mock_check")
            
            mock_lint.side_effect = pass_check
            mock_cov.side_effect = pass_check
            mock_test.side_effect = pass_check
            
            files = [Path("src/test.py"), Path("tests/test_test.py")]
            report = await gate.run_quality_checks(files)
            
            assert report.passed == 3
            assert report.failed == 0
            assert report.is_passing() is True


class TestPreCommitHook:
    """Test pre-commit hook functionality."""

    def test_hook_creation(self):
        """Test creating pre-commit hook."""
        hook = PreCommitHook(
            auto_fix=True,
            run_tests=True,
            check_coverage=True
        )
        
        assert hook.auto_fix is True
        assert hook.run_tests is True
        assert hook.check_coverage is True

    @pytest.mark.asyncio
    async def test_get_staged_files(self):
        """Test getting staged files from git."""
        hook = PreCommitHook()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="src/module.py\ntests/test_module.py\n"
            )
            
            files = await hook._get_staged_files()
            
            assert len(files) == 2
            assert Path("src/module.py") in files
            assert Path("tests/test_module.py") in files

    @pytest.mark.asyncio
    async def test_auto_fix_formatting(self):
        """Test auto-fixing code formatting."""
        hook = PreCommitHook(auto_fix=True)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            result = await hook._auto_fix_formatting([Path("test.py")])
            
            assert result is True
            mock_run.assert_called()

    @pytest.mark.asyncio
    async def test_focused_test_running(self):
        """Test running focused tests based on changed files."""
        hook = PreCommitHook(run_tests=True)
        
        # Mock test discovery
        with patch.object(hook, "_find_related_tests") as mock_find, \
             patch("subprocess.run") as mock_run:
            
            mock_find.return_value = [Path("tests/test_module.py")]
            mock_run.return_value = Mock(returncode=0, stdout="1 passed")
            
            changed_files = [Path("src/module.py")]
            result = await hook._run_focused_tests(changed_files)
            
            assert result is True
            mock_find.assert_called_once_with(changed_files)

    def test_find_related_tests(self):
        """Test finding tests related to changed files."""
        hook = PreCommitHook()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test structure
            src_dir = Path(temp_dir) / "src"
            tests_dir = Path(temp_dir) / "tests"
            src_dir.mkdir()
            tests_dir.mkdir()
            
            # Create files
            (src_dir / "module.py").touch()
            (tests_dir / "test_module.py").touch()
            (tests_dir / "test_other.py").touch()
            
            changed_files = [src_dir / "module.py"]
            related_tests = hook._find_related_tests(changed_files)
            
            # Should find the related test file
            assert tests_dir / "test_module.py" in related_tests
            assert tests_dir / "test_other.py" not in related_tests

    @pytest.mark.asyncio
    async def test_commit_message_validation(self):
        """Test commit message validation."""
        hook = PreCommitHook()
        
        # Valid conventional commit
        assert hook._validate_commit_message("feat: add new feature") is True
        assert hook._validate_commit_message("fix: resolve bug #123") is True
        assert hook._validate_commit_message("docs: update README") is True
        
        # Invalid messages
        assert hook._validate_commit_message("random message") is False
        assert hook._validate_commit_message("FEAT: should be lowercase") is False
        assert hook._validate_commit_message("") is False

    @pytest.mark.asyncio
    async def test_full_pre_commit_flow(self):
        """Test complete pre-commit hook execution."""
        hook = PreCommitHook(auto_fix=True, run_tests=True)
        
        with patch.object(hook, "_get_staged_files") as mock_files, \
             patch.object(hook, "_auto_fix_formatting") as mock_fix, \
             patch.object(hook, "_run_focused_tests") as mock_tests, \
             patch.object(hook, "_validate_commit_message") as mock_msg:
            
            mock_files.return_value = [Path("src/test.py")]
            mock_fix.return_value = True
            mock_tests.return_value = True
            mock_msg.return_value = True
            
            result = await hook.run_pre_commit_checks("feat: add feature")
            
            assert result is True
            mock_files.assert_called_once()
            mock_fix.assert_called_once()
            mock_tests.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_commit_failure_stops_commit(self):
        """Test that pre-commit failures prevent commits."""
        hook = PreCommitHook()
        
        with patch.object(hook, "_get_staged_files") as mock_files, \
             patch.object(hook, "_run_focused_tests") as mock_tests:
            
            mock_files.return_value = [Path("src/test.py")]
            mock_tests.return_value = False  # Tests fail
            
            result = await hook.run_pre_commit_checks("feat: add feature")
            
            assert result is False


class TestCodeTemplate:
    """Test code template system."""

    def test_template_creation(self):
        """Test creating code template."""
        template = CodeTemplate(
            name="mcp_tool",
            description="MCP tool template",
            template_content="def {{name}}(): pass"
        )
        
        assert template.name == "mcp_tool"
        assert template.description == "MCP tool template"
        assert "{{name}}" in template.template_content

    def test_template_rendering(self):
        """Test rendering template with variables."""
        template = CodeTemplate(
            name="function",
            description="Function template", 
            template_content="def {{function_name}}({{params}}):\n    \"\"\"{{docstring}}\"\"\"\n    return {{default_return}}"
        )
        
        result = template.render({
            "function_name": "calculate_sum",
            "params": "a: int, b: int",
            "docstring": "Calculate sum of two numbers",
            "default_return": "a + b"
        })
        
        assert "def calculate_sum(a: int, b: int):" in result
        assert "Calculate sum of two numbers" in result
        assert "return a + b" in result

    def test_template_with_conditionals(self):
        """Test template with conditional logic."""
        template = CodeTemplate(
            name="class_with_init",
            description="Class with optional __init__",
            template_content="""class {{class_name}}:
    \"\"\"{{class_docstring}}\"\"\"
{%- if include_init %}

    def __init__(self{{init_params}}):
        \"\"\"Initialize {{class_name}}.\"\"\"
{%- for param in init_assignments %}
        self.{{param}} = {{param}}
{%- endfor %}
{%- endif %}"""
        )
        
        # With init
        result_with_init = template.render({
            "class_name": "DataProcessor",
            "class_docstring": "Process data efficiently",
            "include_init": True,
            "init_params": ", data: str",
            "init_assignments": ["data"]
        })
        
        assert "class DataProcessor:" in result_with_init
        assert "def __init__(self, data: str):" in result_with_init
        assert "self.data = data" in result_with_init
        
        # Without init
        result_without_init = template.render({
            "class_name": "StaticProcessor", 
            "class_docstring": "Static processor",
            "include_init": False
        })
        
        assert "class StaticProcessor:" in result_without_init
        assert "__init__" not in result_without_init

    def test_invalid_template_handling(self):
        """Test handling of invalid templates."""
        template = CodeTemplate(
            name="broken",
            description="Broken template",
            template_content="def {{missing_var}}(): pass"
        )
        
        # Should handle missing variables gracefully
        with pytest.raises(Exception):  # Template rendering should fail
            template.render({})


class TestAutoGenerator:
    """Test automatic code generation."""

    def test_generator_creation(self):
        """Test creating auto generator."""
        generator = AutoGenerator()
        assert len(generator.templates) >= 0

    def test_register_template(self):
        """Test registering new template."""
        generator = AutoGenerator()
        template = CodeTemplate(
            name="test_template",
            description="Test template",
            template_content="# {{comment}}"
        )
        
        generator.register_template(template)
        assert "test_template" in generator.templates

    def test_generate_mcp_tool(self):
        """Test generating MCP tool code."""
        generator = AutoGenerator()
        
        tool_spec = {
            "name": "search_documents",
            "description": "Search for documents",
            "parameters": [
                {"name": "query", "type": "str", "description": "Search query"},
                {"name": "limit", "type": "int", "description": "Max results", "default": 10}
            ]
        }
        
        code = generator.generate_mcp_tool(tool_spec)
        
        assert "search_documents" in code
        assert "Search for documents" in code
        assert "query: str" in code
        assert "limit: int = 10" in code
        assert "@server.call_tool" in code

    def test_generate_test_file(self):
        """Test generating test file for module."""
        generator = AutoGenerator()
        
        module_info = {
            "name": "calculator",
            "functions": ["add", "subtract", "multiply"],
            "classes": ["Calculator"]
        }
        
        test_code = generator.generate_test_file(module_info)
        
        assert "class TestCalculator:" in test_code
        assert "def test_add" in test_code
        assert "def test_subtract" in test_code
        assert "def test_multiply" in test_code
        assert "import pytest" in test_code

    def test_generate_documentation(self):
        """Test generating documentation from code."""
        generator = AutoGenerator()
        
        code_info = {
            "module": "data_processor",
            "description": "Process various data formats",
            "functions": [
                {
                    "name": "process_csv",
                    "description": "Process CSV files",
                    "params": ["file_path", "delimiter"],
                    "returns": "DataFrame"
                }
            ],
            "classes": [
                {
                    "name": "DataProcessor", 
                    "description": "Main data processing class",
                    "methods": ["load", "transform", "save"]
                }
            ]
        }
        
        docs = generator.generate_documentation(code_info)
        
        assert "# data_processor" in docs
        assert "Process various data formats" in docs
        assert "## Functions" in docs
        assert "### process_csv" in docs
        assert "## Classes" in docs
        assert "### DataProcessor" in docs

    @pytest.mark.asyncio
    async def test_analyze_and_generate(self):
        """Test analyzing existing code and generating improvements."""
        generator = AutoGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample module
            module_file = Path(temp_dir) / "sample.py"
            module_file.write_text("""
def calculate(a, b):
    return a + b

class Calculator:
    def add(self, x, y):
        return x + y
""")
            
            # Analyze and generate
            suggestions = await generator.analyze_and_generate([module_file])
            
            assert len(suggestions) > 0
            # Should suggest missing docstrings, type hints, tests
            suggestion_types = [s["type"] for s in suggestions]
            assert "missing_docstring" in suggestion_types
            assert "missing_type_hints" in suggestion_types
            assert "missing_tests" in suggestion_types

    def test_load_builtin_templates(self):
        """Test loading built-in code templates."""
        generator = AutoGenerator()
        generator.load_builtin_templates()
        
        # Should have common templates
        assert "mcp_tool" in generator.templates
        assert "test_class" in generator.templates
        assert "pydantic_model" in generator.templates

    @pytest.mark.asyncio
    async def test_generate_from_pattern(self):
        """Test generating code from detected patterns."""
        generator = AutoGenerator()
        
        # Pattern: Functions without docstrings
        pattern = {
            "type": "missing_docstring",
            "location": "src/utils.py:15",
            "function_name": "helper_function",
            "params": ["data", "options"]
        }
        
        suggestion = await generator.generate_from_pattern(pattern)
        
        assert suggestion["type"] == "add_docstring"
        assert "helper_function" in suggestion["generated_code"]
        assert '"""' in suggestion["generated_code"]


class TestIntegration:
    """Test integration between quality automation components."""

    @pytest.mark.asyncio
    async def test_pre_commit_with_auto_generation(self):
        """Test pre-commit hook with automatic code generation."""
        hook = PreCommitHook(auto_fix=True)
        generator = AutoGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with issues
            problem_file = Path(temp_dir) / "issues.py"
            problem_file.write_text("def func(x,y):return x+y")  # Poor formatting, no docstring
            
            # Mock staged files
            with patch.object(hook, "_get_staged_files") as mock_files:
                mock_files.return_value = [problem_file]
                
                # Analyze and suggest improvements
                suggestions = await generator.analyze_and_generate([problem_file])
                
                assert len(suggestions) > 0
                # Should find formatting and documentation issues
                
    @pytest.mark.asyncio
    async def test_quality_gate_with_auto_fixes(self):
        """Test quality gate that auto-fixes issues when possible."""
        gate = QualityGate(auto_fix_enabled=True)
        generator = AutoGenerator()
        
        with patch("subprocess.run") as mock_run:
            # First run finds issues
            mock_run.side_effect = [
                Mock(returncode=1, stderr="Formatting issues found"),  # Initial linting fails
                Mock(returncode=0, stdout="Fixed formatting"),          # Auto-fix succeeds  
                Mock(returncode=0, stdout="All checks passed")          # Re-run passes
            ]
            
            files = [Path("test.py")]
            report = await gate.run_quality_checks(files)
            
            # Should pass after auto-fixing
            assert report.is_passing() is True
            assert mock_run.call_count == 3  # Initial check, fix, re-check

    @pytest.mark.asyncio 
    async def test_full_automation_workflow(self):
        """Test complete code quality automation workflow."""
        hook = PreCommitHook(auto_fix=True, run_tests=True)
        gate = QualityGate(min_coverage=80.0, auto_fix_enabled=True)
        generator = AutoGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample codebase
            src_file = Path(temp_dir) / "src" / "module.py"
            src_file.parent.mkdir()
            src_file.write_text("def func(): pass")
            
            test_file = Path(temp_dir) / "tests" / "test_module.py"
            test_file.parent.mkdir()
            
            # Step 1: Pre-commit analysis
            with patch.object(hook, "_get_staged_files") as mock_staged:
                mock_staged.return_value = [src_file]
                
                # Step 2: Auto-generation of missing tests
                suggestions = await generator.analyze_and_generate([src_file])
                missing_tests = [s for s in suggestions if s["type"] == "missing_tests"]
                
                if missing_tests:
                    # Generate test file
                    test_code = generator.generate_test_file({
                        "name": "module",
                        "functions": ["func"],
                        "classes": []
                    })
                    test_file.write_text(test_code)
                
                # Step 3: Quality gate validation
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = Mock(returncode=0, stdout="All good")
                    
                    report = await gate.run_quality_checks([src_file, test_file])
                    
                    # Should pass with generated tests
                    assert report.is_passing() is True
"""Tests for kernel/capability_assessment.py."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kernel.capability_assessment import CapabilityAssessor


@pytest.fixture
def assessor():
    """Create a CapabilityAssessor instance."""
    return CapabilityAssessor()


@pytest.fixture
def sample_skills():
    """Sample skills list for testing."""
    return [
        {
            "name": "api-skill",
            "tags": ["api", "rest", "http"],
            "description": "Building REST APIs with endpoints",
        },
        {
            "name": "testing-skill",
            "tags": ["testing", "pytest", "coverage"],
            "description": "Writing tests and test coverage",
        },
        {
            "name": "database-skill",
            "tags": ["database", "sql", "postgres"],
            "description": "Database design and queries",
        },
    ]


class TestAssessCapabilities:
    """Tests for assess_capabilities method."""

    def test_assess_full_coverage(self, assessor, sample_skills):
        """Goal words all match skill tags => confidence near 1.0."""
        goal = "rest api testing coverage"
        result = assessor.assess_capabilities(goal, sample_skills)
        assert result["confidence"] == 1.0
        assert len(result["gaps"]) == 0
        assert "api-skill" in result["covered"]
        assert "testing-skill" in result["covered"]

    def test_assess_no_coverage(self, assessor):
        """Goal words match nothing => confidence 0.0, gaps populated."""
        skills = [
            {"name": "cooking-skill", "tags": ["cooking", "food"], "description": "Making food"},
        ]
        goal = "deploy kubernetes cluster"
        result = assessor.assess_capabilities(goal, skills)
        assert result["confidence"] == 0.0
        assert "deploy" in result["gaps"]
        assert "kubernetes" in result["gaps"]
        assert "cluster" in result["gaps"]
        assert result["covered"] == []

    def test_assess_partial_coverage(self, assessor, sample_skills):
        """Some matches => confidence between 0.3 and 0.7."""
        goal = "rest api kubernetes deployment"
        result = assessor.assess_capabilities(goal, sample_skills)
        assert 0.0 < result["confidence"] < 1.0
        assert len(result["gaps"]) > 0
        assert "api-skill" in result["covered"]
        assert "kubernetes" in result["gaps"]
        assert "deployment" in result["gaps"]

    def test_assess_empty_goal(self, assessor, sample_skills):
        """Empty goal returns confidence 0.0, empty covered/gaps."""
        result = assessor.assess_capabilities("", sample_skills)
        assert result["confidence"] == 0.0
        assert result["covered"] == []
        assert result["gaps"] == []

    def test_assess_empty_skills(self, assessor):
        """Empty skills returns confidence 0.0, all goal words as gaps."""
        goal = "rest api testing"
        result = assessor.assess_capabilities(goal, [])
        assert result["confidence"] == 0.0
        assert result["covered"] == []
        assert "rest" in result["gaps"]
        assert "api" in result["gaps"]
        assert "testing" in result["gaps"]

    def test_assess_whitespace_only_goal(self, assessor, sample_skills):
        """Whitespace-only goal returns confidence 0.0."""
        result = assessor.assess_capabilities("   ", sample_skills)
        assert result["confidence"] == 0.0
        assert result["covered"] == []
        assert result["gaps"] == []

    def test_assess_filters_stop_words(self, assessor, sample_skills):
        """Common words like 'build', 'a', 'the' not counted as gaps."""
        goal = "build a rest api for the web"
        result = assessor.assess_capabilities(goal, sample_skills)
        # "build", "a", "the", "for" are stop words, should not appear in gaps
        assert "build" not in result["gaps"]
        assert "the" not in result["gaps"]
        assert "for" not in result["gaps"]
        # "rest" and "api" should match
        assert "api-skill" in result["covered"]

    def test_assess_filters_short_words(self, assessor, sample_skills):
        """Words shorter than 3 chars are filtered out."""
        goal = "an api to go"
        result = assessor.assess_capabilities(goal, sample_skills)
        # "an" and "to" and "go" are < 3 chars or stop words
        assert "an" not in result["gaps"]
        assert "to" not in result["gaps"]

    def test_assess_matches_description_words(self, assessor):
        """Skills match on description words too, not just tags."""
        skills = [
            {"name": "web-skill", "tags": ["web"], "description": "frontend development"},
        ]
        goal = "frontend web application"
        result = assessor.assess_capabilities(goal, skills)
        assert "web-skill" in result["covered"]
        # "frontend" is in description, should be matched
        assert "frontend" not in result["gaps"]


class TestIdentifySkillGaps:
    """Tests for identify_skill_gaps method."""

    def test_identify_gaps(self, assessor):
        """Keywords not in tags returned as gaps."""
        keywords = ["api", "kubernetes", "testing", "docker"]
        tags = ["api", "testing", "rest"]
        result = assessor.identify_skill_gaps(keywords, tags)
        assert "kubernetes" in result
        assert "docker" in result
        assert "api" not in result
        assert "testing" not in result

    def test_identify_gaps_all_matched(self, assessor):
        """Returns empty list when all keywords have matching tags."""
        keywords = ["api", "testing"]
        tags = ["api", "testing", "rest", "coverage"]
        result = assessor.identify_skill_gaps(keywords, tags)
        assert result == []

    def test_identify_gaps_case_insensitive(self, assessor):
        """Gap detection is case-insensitive."""
        keywords = ["api", "rest"]
        tags = ["API", "REST"]
        result = assessor.identify_skill_gaps(keywords, tags)
        assert result == []

    def test_identify_gaps_empty_keywords(self, assessor):
        """Empty keywords returns empty list."""
        result = assessor.identify_skill_gaps([], ["api", "rest"])
        assert result == []

    def test_identify_gaps_empty_tags(self, assessor):
        """Empty tags means all keywords are gaps."""
        keywords = ["api", "rest"]
        result = assessor.identify_skill_gaps(keywords, [])
        assert result == ["api", "rest"]


class TestSuggestSkillCreation:
    """Tests for suggest_skill_creation method."""

    def test_suggest_skill_creation(self, assessor):
        """Returns one suggestion per gap."""
        gaps = ["kubernetes", "docker"]
        result = assessor.suggest_skill_creation(gaps)
        assert len(result) == 2
        assert result[0] == {
            "name": "kubernetes-skill",
            "description": "Skill for kubernetes development",
            "tags": ["kubernetes"],
        }
        assert result[1] == {
            "name": "docker-skill",
            "description": "Skill for docker development",
            "tags": ["docker"],
        }

    def test_suggest_skill_creation_empty(self, assessor):
        """Returns empty list for no gaps."""
        result = assessor.suggest_skill_creation([])
        assert result == []

    def test_suggest_skill_creation_single_gap(self, assessor):
        """Single gap returns single suggestion."""
        result = assessor.suggest_skill_creation(["monitoring"])
        assert len(result) == 1
        assert result[0]["name"] == "monitoring-skill"
        assert result[0]["tags"] == ["monitoring"]


class TestWriteAssessment:
    """Tests for write_assessment method."""

    def test_write_assessment(self, assessor, tmp_path):
        """Writes YAML file to memory dir with correct keys."""
        memory_dir = str(tmp_path / "memory")
        Path(memory_dir).mkdir()
        assessment = {
            "covered": ["api-skill"],
            "gaps": ["kubernetes"],
            "confidence": 0.5,
        }
        assessor.write_assessment(assessment, "build api on kubernetes", memory_dir)

        assessment_path = Path(memory_dir) / "assessment.yaml"
        assert assessment_path.exists()
        with open(assessment_path, "r") as f:
            data = yaml.safe_load(f)

        assert data["goal"] == "build api on kubernetes"
        assert data["confidence"] == 0.5
        assert data["covered_skills"] == ["api-skill"]
        assert data["skill_gaps"] == ["kubernetes"]
        assert data["suggestions"] == [
            {
                "name": "kubernetes-skill",
                "description": "Skill for kubernetes development",
                "tags": ["kubernetes"],
            }
        ]
        assert "timestamp" in data

    def test_write_assessment_creates_dir(self, assessor, tmp_path):
        """Creates memory dir if missing."""
        memory_dir = str(tmp_path / "new_memory")
        assessment = {"covered": [], "gaps": [], "confidence": 0.0}
        assessor.write_assessment(assessment, "test goal", memory_dir)

        assert Path(memory_dir).exists()
        assert (Path(memory_dir) / "assessment.yaml").exists()

    def test_write_assessment_no_gaps(self, assessor, tmp_path):
        """Assessment with no gaps produces empty suggestions."""
        memory_dir = str(tmp_path / "memory")
        Path(memory_dir).mkdir()
        assessment = {"covered": ["skill-a"], "gaps": [], "confidence": 1.0}
        assessor.write_assessment(assessment, "covered goal", memory_dir)

        with open(Path(memory_dir) / "assessment.yaml", "r") as f:
            data = yaml.safe_load(f)
        assert data["suggestions"] == []


class TestRunnerIntegration:
    """Tests for capability assessment integration in runner.py."""

    def test_runner_integration_low_confidence(self, tmp_path, capsys):
        """Warning is printed when confidence is low."""
        import runner

        # Create minimal kernel structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create graph.yaml
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/init.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 1,
                }
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        # Create state.yaml
        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "goal": "",
            "status": "idle",
            "errors": [],
            "context": {},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        # Create skills index with no relevant skills
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump(
                {
                    "items": [
                        {
                            "name": "cooking-skill",
                            "tags": ["cooking"],
                            "description": "food prep",
                            "path": "cooking",
                            "composable_with": [],
                        }
                    ]
                },
                f,
            )
        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        # Patch KERNEL_ROOT to use our tmp structure
        with patch.object(runner, "KERNEL_ROOT", tmp_path):
            runner.main(["--goal", "deploy kubernetes cluster monitoring"])

        captured = capsys.readouterr()
        assert "[WARNING] Low skill coverage" in captured.err
        assert "Consider creating skills" in captured.err

    def test_runner_integration_high_confidence(self, tmp_path, capsys):
        """No warning printed when confidence is high."""
        import runner

        # Create minimal kernel structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create graph.yaml
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/init.md",
                    "description": "Init",
                    "transitions": [],
                    "max_retries": 1,
                }
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        # Create state.yaml
        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "goal": "",
            "status": "idle",
            "errors": [],
            "context": {},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        # Create skills index with skills matching the goal
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump(
                {
                    "items": [
                        {
                            "name": "api-skill",
                            "tags": ["api", "rest", "http"],
                            "description": "Building REST APIs",
                            "path": "api",
                            "composable_with": [],
                        },
                        {
                            "name": "testing-skill",
                            "tags": ["testing", "pytest"],
                            "description": "Writing tests",
                            "path": "testing",
                            "composable_with": [],
                        },
                    ]
                },
                f,
            )
        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        # Patch KERNEL_ROOT to use our tmp structure
        with patch.object(runner, "KERNEL_ROOT", tmp_path):
            runner.main(["--goal", "rest api testing"])

        captured = capsys.readouterr()
        assert "[WARNING]" not in captured.err
        assert "[NOTE]" not in captured.err

    def test_runner_dry_run_skips_assessment(self, tmp_path, capsys):
        """Dry-run mode does not run capability assessment."""
        import runner

        with patch.object(runner, "KERNEL_ROOT", tmp_path):
            # Create minimal structure for dry-run
            kernel_dir = tmp_path / "kernel"
            kernel_dir.mkdir()
            memory_dir = tmp_path / "memory"
            memory_dir.mkdir()
            knowledge_dir = tmp_path / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "rules").mkdir()
            (knowledge_dir / "patterns").mkdir()

            # Skills directory is a sibling of knowledge/
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()

            graph_data = {
                "nodes": [
                    {
                        "id": "init",
                        "prompt_file": "prompts/init.md",
                        "description": "Init",
                        "transitions": [],
                        "max_retries": 1,
                    }
                ],
                "default_start": "init",
                "max_iterations": 30,
            }
            with open(kernel_dir / "graph.yaml", "w") as f:
                yaml.safe_dump(graph_data, f)
            state_data = {
                "current_node": "init",
                "iteration_count": 0,
                "goal": "",
                "status": "idle",
                "errors": [],
                "context": {},
            }
            with open(kernel_dir / "state.yaml", "w") as f:
                yaml.safe_dump(state_data, f)
            with open(skills_dir / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)
            with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)
            with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

            runner.main(["--goal", "deploy kubernetes", "--dry-run"])

        # No assessment.yaml should be created in dry-run
        assessment_path = tmp_path / "memory" / "assessment.yaml"
        assert not assessment_path.exists()

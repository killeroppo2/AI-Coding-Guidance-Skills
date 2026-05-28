"""Tests for the skill factory module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from kernel.evolution.engine import EvolutionEngine
from kernel.skill_factory import SkillFactory


class TestValidateSkillName:
    """Tests for SkillFactory.validate_skill_name()."""

    def test_valid_simple_name(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("a")
        assert valid is True
        assert reason == ""

    def test_valid_kebab_case(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("my-skill")
        assert valid is True
        assert reason == ""

    def test_valid_with_numbers(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("test-123")
        assert valid is True
        assert reason == ""

    def test_valid_multi_segment(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("hello-world-foo")
        assert valid is True
        assert reason == ""

    def test_reject_empty(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("")
        assert valid is False
        assert "empty" in reason.lower()

    def test_reject_uppercase(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("MySkill")
        assert valid is False
        assert "lowercase" in reason.lower()

    def test_reject_spaces(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("my skill")
        assert valid is False
        assert "space" in reason.lower()

    def test_reject_leading_hyphen(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("-leading")
        assert valid is False
        assert "start" in reason.lower()

    def test_reject_trailing_hyphen(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("trailing-")
        assert valid is False
        assert "end" in reason.lower()

    def test_reject_double_hyphen(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("double--hyphen")
        assert valid is False
        assert "double" in reason.lower()

    def test_reject_special_chars(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        valid, reason = factory.validate_skill_name("special!chars")
        assert valid is False
        assert "kebab" in reason.lower()


class TestCreateSkill:
    """Tests for SkillFactory.create_skill()."""

    def test_creates_directory_and_skill_md(self, tmp_knowledge: Path, tmp_path: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        result = factory.create_skill("my-skill", "A test skill", "Some content here")

        assert result == tmp_path / "skills" / "my-skill"
        assert result.is_dir()
        skill_md = result / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text(encoding="utf-8")
        assert content == "# my-skill\n\nA test skill\n\nSome content here"

    def test_registers_in_index(self, tmp_knowledge: Path, tmp_path: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        factory.create_skill("my-skill", "A test skill", "Content", ["python", "testing"])

        index_path = tmp_path / "skills" / "_index.yaml"
        with open(index_path, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f)

        assert len(index["items"]) == 1
        item = index["items"][0]
        assert item["name"] == "my-skill"
        assert item["description"] == "A test skill"
        assert item["tags"] == ["python", "testing"]
        assert item["path"] == "my-skill"

    def test_raises_value_error_for_invalid_name(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        with pytest.raises(ValueError, match="Invalid skill name"):
            factory.create_skill("Invalid Name", "desc", "content")

    def test_tags_default_to_empty_list(self, tmp_knowledge: Path, tmp_path: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        factory.create_skill("no-tags", "No tags skill", "Content")

        index_path = tmp_path / "skills" / "_index.yaml"
        with open(index_path, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f)

        item = index["items"][0]
        assert item["tags"] == []


class TestCreateSkillFromTemplate:
    """Tests for SkillFactory.create_skill_from_template()."""

    def test_generates_sections_in_skill_md(self, tmp_knowledge: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        sections = {
            "overview": "This is an overview.",
            "usage": "Use it like this.",
        }
        result = factory.create_skill_from_template(
            "template-skill", "A template skill", sections, ["template"]
        )

        skill_md = result / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        assert "# template-skill" in content
        assert "A template skill" in content
        assert "## Overview" in content
        assert "This is an overview." in content
        assert "## Usage" in content
        assert "Use it like this." in content

    def test_registers_in_index(self, tmp_knowledge: Path, tmp_path: Path) -> None:
        factory = SkillFactory(str(tmp_knowledge))
        sections = {"overview": "Overview content."}
        factory.create_skill_from_template("tmpl-skill", "Template", sections, ["ai"])

        index_path = tmp_path / "skills" / "_index.yaml"
        with open(index_path, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f)

        assert len(index["items"]) == 1
        assert index["items"][0]["name"] == "tmpl-skill"


class TestEvolutionEngineAddSkill:
    """Integration test for EvolutionEngine apply_change with add_skill."""

    def test_apply_change_add_skill_creates_skill(self, tmp_path: Path) -> None:
        # Set up directory structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        # Create empty index
        index_path = skills_dir / "_index.yaml"
        with open(index_path, "w") as f:
            yaml.safe_dump({"items": []}, f)

        # Create mock graph executor
        graph_executor = MagicMock()

        engine = EvolutionEngine(str(kernel_dir), graph_executor)

        change = engine.propose_change(
            "add_skill",
            {
                "name": "test-skill",
                "description": "A test skill",
                "content": "Test content body",
                "tags": ["testing"],
            },
            "Testing skill creation via evolution engine",
        )

        result = engine.apply_change(change)

        assert result is True
        # Verify skill was created
        skill_dir = skills_dir / "test-skill"
        assert skill_dir.is_dir()
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text(encoding="utf-8")
        assert "# test-skill" in content
        assert "A test skill" in content
        assert "Test content body" in content

        # Verify index was updated
        with open(index_path, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f)
        assert len(index["items"]) == 1
        assert index["items"][0]["name"] == "test-skill"
        assert index["items"][0]["tags"] == ["testing"]

    def test_apply_change_add_skill_invalid_name_fails(self, tmp_path: Path) -> None:
        # Set up directory structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        index_path = skills_dir / "_index.yaml"
        with open(index_path, "w") as f:
            yaml.safe_dump({"items": []}, f)

        graph_executor = MagicMock()
        engine = EvolutionEngine(str(kernel_dir), graph_executor)

        change = engine.propose_change(
            "add_skill",
            {
                "name": "Invalid Name",
                "description": "Bad name",
                "content": "Content",
                "tags": [],
            },
            "Should fail due to invalid name",
        )

        result = engine.apply_change(change)

        # ValueError is caught and logged as failed
        assert result is False

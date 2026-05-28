"""Tests for kernel/skill_selector.py - skill auto-selection."""

from pathlib import Path

import pytest
import yaml

import runner
from kernel.skill_selector import select_skills_for_goal


class TestSelectSkillsForGoal:
    """Tests for the select_skills_for_goal function."""

    def test_empty_goal_returns_empty(self) -> None:
        """Test that an empty goal string returns an empty list."""
        skills = [
            {"name": "tdd", "tags": ["testing", "tdd"], "description": "Test-driven development"},
        ]
        assert select_skills_for_goal("", skills) == []

    def test_whitespace_goal_returns_empty(self) -> None:
        """Test that a whitespace-only goal returns an empty list."""
        skills = [
            {"name": "tdd", "tags": ["testing", "tdd"], "description": "Test-driven development"},
        ]
        assert select_skills_for_goal("   ", skills) == []

    def test_empty_skills_returns_empty(self) -> None:
        """Test that empty available_skills returns an empty list."""
        assert select_skills_for_goal("Build an API", []) == []

    def test_coding_goal_selects_coding_skills(self) -> None:
        """Test that a coding goal selects execution/coding-related skills."""
        skills = [
            {"name": "ralph", "tags": ["execution", "autonomous", "coding"],
             "description": "Autonomous coding agent"},
            {"name": "tdd", "tags": ["testing", "tdd", "quality"],
             "description": "Test-driven development"},
            {"name": "ui-ux-pro-max", "tags": ["design", "ui", "ux", "frontend"],
             "description": "UI/UX design intelligence"},
            {"name": "prd", "tags": ["planning", "requirements", "documentation"],
             "description": "Generate Product Requirements Documents"},
        ]
        result = select_skills_for_goal("coding execution autonomous testing", skills)
        assert "ralph" in result
        assert "tdd" in result

    def test_design_goal_selects_design_skills(self) -> None:
        """Test that a design goal selects design-related skills."""
        skills = [
            {"name": "ui-ux-pro-max", "tags": ["design", "ui", "ux", "frontend"],
             "description": "UI/UX design intelligence"},
            {"name": "brand", "tags": ["brand", "identity", "guidelines"],
             "description": "Brand identity management"},
            {"name": "tdd", "tags": ["testing", "tdd", "quality"],
             "description": "Test-driven development"},
            {"name": "design", "tags": ["design", "logo", "icons", "branding"],
             "description": "Comprehensive design skill"},
        ]
        result = select_skills_for_goal("design UI frontend", skills)
        assert "ui-ux-pro-max" in result
        assert "design" in result

    def test_max_skills_limits_output(self) -> None:
        """Test that max_skills parameter limits the number of results."""
        skills = [
            {"name": f"skill-{i}", "tags": ["common"], "description": "A common skill"}
            for i in range(10)
        ]
        result = select_skills_for_goal("common", skills, max_skills=3)
        assert len(result) <= 3

    def test_scores_weight_tags_higher(self) -> None:
        """Test that tag matches score higher than description-only matches."""
        skills = [
            {"name": "tag-match", "tags": ["testing"],
             "description": "Something unrelated"},
            {"name": "desc-match", "tags": ["unrelated"],
             "description": "This is about testing things"},
        ]
        result = select_skills_for_goal("testing", skills)
        # tag-match has tag score 3, desc-match has desc score 1
        assert result[0] == "tag-match"

    def test_no_matches_returns_empty(self) -> None:
        """Test that completely unrelated goal returns empty list."""
        skills = [
            {"name": "tdd", "tags": ["testing", "tdd"],
             "description": "Test-driven development"},
        ]
        result = select_skills_for_goal("quantum physics calculations", skills)
        assert result == []

    def test_skills_with_score_zero_excluded(self) -> None:
        """Test that skills with zero score are excluded from results."""
        skills = [
            {"name": "relevant", "tags": ["api"],
             "description": "Build API services"},
            {"name": "irrelevant", "tags": ["design"],
             "description": "UI design patterns"},
        ]
        result = select_skills_for_goal("api", skills)
        assert "relevant" in result
        assert "irrelevant" not in result

    def test_missing_tags_handled(self) -> None:
        """Test that skills without tags field are handled gracefully."""
        skills = [
            {"name": "no-tags", "description": "A skill without tags"},
            {"name": "has-tags", "tags": ["coding"],
             "description": "A skill with tags"},
        ]
        result = select_skills_for_goal("coding", skills)
        assert "has-tags" in result

    def test_missing_description_handled(self) -> None:
        """Test that skills without description field are handled gracefully."""
        skills = [
            {"name": "no-desc", "tags": ["coding"]},
            {"name": "has-desc", "tags": ["design"],
             "description": "Design stuff"},
        ]
        result = select_skills_for_goal("coding", skills)
        assert "no-desc" in result


class TestRunnerSkillAutoSelection:
    """Tests for skill auto-selection integration in runner.py."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan",
                    "transitions": [],
                    "max_retries": 1,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt")
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump({"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "patterns"]:
            (knowledge_dir / sub).mkdir()

        # Skills directory is now a sibling of knowledge/ at project root
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Add some skills to the index
        skills_index = {
            "items": [
                {"name": "tdd", "path": "tdd", "tags": ["testing", "tdd", "quality"],
                 "description": "Test-driven development", "composable_with": []},
                {"name": "ralph", "path": "ralph", "tags": ["execution", "autonomous", "coding"],
                 "description": "Autonomous coding agent", "composable_with": []},
                {"name": "ui-ux-pro-max", "path": "ui-ux-pro-max", "tags": ["design", "ui", "ux"],
                 "description": "UI/UX design intelligence", "composable_with": []},
            ]
        }
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump(skills_index, f)

        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_runner_auto_selects_skills(self, runner_env: Path, monkeypatch) -> None:
        """Test that runner auto-selects skills based on goal and stores in state."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "testing tdd quality",
            "--dry-run",
            "--max-iterations", "1",
        ])
        skills_loaded = state.get("context", {}).get("skills_loaded", [])
        assert "tdd" in skills_loaded

    def test_runner_skills_flag_override(self, runner_env: Path, monkeypatch) -> None:
        """Test that --skills flag overrides auto-selection."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "testing tdd quality",
            "--skills", "ralph,ui-ux-pro-max",
            "--dry-run",
            "--max-iterations", "1",
        ])
        skills_loaded = state.get("context", {}).get("skills_loaded", [])
        assert skills_loaded == ["ralph", "ui-ux-pro-max"]

    def test_runner_skills_flag_empty_string(self, runner_env: Path, monkeypatch) -> None:
        """Test that --skills with empty value results in empty list."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "testing",
            "--skills", "",
            "--dry-run",
            "--max-iterations", "1",
        ])
        skills_loaded = state.get("context", {}).get("skills_loaded", [])
        assert skills_loaded == []

    def test_runner_no_matching_skills(self, runner_env: Path, monkeypatch) -> None:
        """Test that unrelated goal gets empty skills list."""
        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)
        state = runner.main([
            "--goal", "quantum physics simulation",
            "--dry-run",
            "--max-iterations", "1",
        ])
        skills_loaded = state.get("context", {}).get("skills_loaded", [])
        assert skills_loaded == []


class TestContextAssemblerLoadsContent:
    """Tests for context_assembler._load_skills using SkillComposer."""

    def test_context_assembler_loads_content(self, tmp_path: Path) -> None:
        """Test that _load_skills uses SkillComposer when SKILL.md is available."""
        from kernel.context_assembler import ContextAssembler
        from knowledge.store import KnowledgeStore

        # Set up knowledge dir with a skill that has SKILL.md
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create skill directory with SKILL.md
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill\n\nThis is the skill content.")

        # Register skill in index
        index_data = {
            "items": [
                {"name": "test-skill", "path": "test-skill",
                 "description": "A test skill", "tags": ["test"],
                 "composable_with": []},
            ]
        }
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)
        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        store = KnowledgeStore(str(knowledge_dir))
        assembler = ContextAssembler(tmp_path)

        result = assembler._load_skills(["test-skill"], store)
        assert "Test Skill" in result
        assert "This is the skill content." in result

    def test_context_assembler_fallback_on_missing_skill(self, tmp_path: Path) -> None:
        """Test that _load_skills falls back to descriptions when SKILL.md is missing."""
        from kernel.context_assembler import ContextAssembler
        from knowledge.store import KnowledgeStore

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Register skill in index but no SKILL.md exists
        index_data = {
            "items": [
                {"name": "missing-skill", "path": "missing-skill",
                 "description": "A skill with no SKILL.md", "tags": [],
                 "composable_with": []},
            ]
        }
        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)
        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        store = KnowledgeStore(str(knowledge_dir))
        assembler = ContextAssembler(tmp_path)

        result = assembler._load_skills(["missing-skill"], store)
        # Should fall back to description
        assert "missing-skill" in result
        assert "A skill with no SKILL.md" in result

    def test_context_assembler_fallback_on_unknown_skill(self, tmp_path: Path) -> None:
        """Test that _load_skills handles completely unknown skills gracefully."""
        from kernel.context_assembler import ContextAssembler
        from knowledge.store import KnowledgeStore

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "rules").mkdir()
        (knowledge_dir / "patterns").mkdir()

        # Skills directory is a sibling of knowledge/
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        with open(skills_dir / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "rules" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)
        with open(knowledge_dir / "patterns" / "_index.yaml", "w") as f:
            yaml.safe_dump({"items": []}, f)

        store = KnowledgeStore(str(knowledge_dir))
        assembler = ContextAssembler(tmp_path)

        result = assembler._load_skills(["nonexistent-skill"], store)
        # Should fall back and show "skill not found"
        assert "nonexistent-skill" in result
        assert "(skill not found)" in result


class TestParseArgsSkills:
    """Tests for the --skills CLI argument."""

    def test_skills_argument(self) -> None:
        """Test parsing --skills argument."""
        args = runner.parse_args(["--goal", "test", "--skills", "tdd,ralph"])
        assert args.skills == "tdd,ralph"

    def test_skills_default_none(self) -> None:
        """Test that --skills defaults to None."""
        args = runner.parse_args(["--goal", "test"])
        assert args.skills is None

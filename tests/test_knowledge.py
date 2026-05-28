"""Tests for the knowledge package."""

from pathlib import Path

import pytest
import yaml

from knowledge.skill_composer import SkillComposer
from knowledge.store import KnowledgeStore


class TestKnowledgeStructure:
    """Tests for knowledge directory structure."""

    def test_knowledge_package_importable(self) -> None:
        """Test that knowledge package can be imported."""
        import knowledge
        assert knowledge is not None

    def test_store_importable(self) -> None:
        """Test that knowledge.store can be imported."""
        from knowledge import store
        assert store is not None

    def test_knowledge_store_class_exists(self) -> None:
        """Test that KnowledgeStore class exists."""
        from knowledge.store import KnowledgeStore
        assert KnowledgeStore is not None

    def test_knowledge_store_instantiation(self, tmp_knowledge: Path) -> None:
        """Test that KnowledgeStore can be instantiated."""
        ks = KnowledgeStore(str(tmp_knowledge))
        assert ks.knowledge_root == tmp_knowledge

    def test_skill_composer_importable(self) -> None:
        """Test that knowledge.skill_composer can be imported."""
        from knowledge.skill_composer import SkillComposer
        assert SkillComposer is not None


class TestKnowledgeStoreRules:
    """Tests for KnowledgeStore rule operations."""

    def test_add_manual_rule(self, tmp_knowledge: Path) -> None:
        """Test adding a manual rule."""
        ks = KnowledgeStore(str(tmp_knowledge))
        rule = {
            "name": "test_rule",
            "description": "A test rule",
            "content": "Always test your code",
            "tags": ["testing", "quality"],
            "source": "manual",
        }
        ks.add_rule(rule, learned=False)
        rules = ks.get_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "test_rule"

    def test_add_learned_rule(self, tmp_knowledge: Path) -> None:
        """Test adding a learned rule."""
        ks = KnowledgeStore(str(tmp_knowledge))
        rule = {
            "name": "learned_pattern",
            "description": "A learned pattern",
            "content": "Smaller functions are better",
            "tags": ["learned", "refactoring"],
            "source": "reflector",
        }
        ks.add_rule(rule, learned=True)
        # Check it was stored in learned/
        assert (tmp_knowledge / "rules" / "learned" / "learned_pattern.yaml").exists()

    def test_get_rules_no_filter(self, tmp_knowledge: Path) -> None:
        """Test getting all rules without filter."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_rule({"name": "r1", "tags": ["a"], "description": "", "content": "", "source": ""})
        ks.add_rule({"name": "r2", "tags": ["b"], "description": "", "content": "", "source": ""})
        rules = ks.get_rules()
        assert len(rules) == 2

    def test_get_rules_with_filter(self, tmp_knowledge: Path) -> None:
        """Test getting rules filtered by tags."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_rule({"name": "r1", "tags": ["testing"], "description": "", "content": "", "source": ""})
        ks.add_rule({"name": "r2", "tags": ["quality"], "description": "", "content": "", "source": ""})
        rules = ks.get_rules(filter_tags=["testing"])
        assert len(rules) == 1
        assert rules[0]["name"] == "r1"


class TestKnowledgeStoreSkills:
    """Tests for KnowledgeStore skill operations."""

    def test_add_skill(self, tmp_knowledge: Path) -> None:
        """Test adding a skill."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("grill-me", "Interview preparation skill", tags=["interview"])
        skills = ks.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "grill-me"

    def test_get_skill(self, tmp_knowledge: Path) -> None:
        """Test getting a skill by name."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("test-skill", "A test skill", tags=["test"], path="test-skill")
        skill = ks.get_skill("test-skill")
        assert skill["name"] == "test-skill"
        assert skill["description"] == "A test skill"

    def test_get_nonexistent_skill(self, tmp_knowledge: Path) -> None:
        """Test that getting a nonexistent skill raises KeyError."""
        ks = KnowledgeStore(str(tmp_knowledge))
        with pytest.raises(KeyError, match="Skill not found"):
            ks.get_skill("nonexistent")

    def test_list_skills_with_tags(self, tmp_knowledge: Path) -> None:
        """Test listing skills filtered by tags."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("s1", "Skill 1", tags=["code"])
        ks.add_skill("s2", "Skill 2", tags=["review"])
        ks.add_skill("s3", "Skill 3", tags=["code", "review"])
        skills = ks.list_skills(tags=["code"])
        assert len(skills) == 2

    def test_list_skills_no_filter(self, tmp_knowledge: Path) -> None:
        """Test listing all skills."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("s1", "Skill 1")
        ks.add_skill("s2", "Skill 2")
        skills = ks.list_skills()
        assert len(skills) == 2


class TestKnowledgeStorePatterns:
    """Tests for KnowledgeStore pattern operations."""

    def test_add_pattern(self, tmp_knowledge: Path) -> None:
        """Test adding a pattern."""
        ks = KnowledgeStore(str(tmp_knowledge))
        pattern = {
            "name": "singleton",
            "description": "Singleton pattern",
            "content": "class Singleton: ...",
            "tags": ["design-pattern"],
            "context": "When you need a single instance",
        }
        ks.add_pattern(pattern)
        patterns = ks.get_patterns()
        assert len(patterns) == 1
        assert patterns[0]["name"] == "singleton"

    def test_get_patterns_with_filter(self, tmp_knowledge: Path) -> None:
        """Test getting patterns filtered by tags."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_pattern({"name": "p1", "tags": ["arch"], "description": "", "content": "", "context": ""})
        ks.add_pattern({"name": "p2", "tags": ["code"], "description": "", "content": "", "context": ""})
        patterns = ks.get_patterns(filter_tags=["arch"])
        assert len(patterns) == 1
        assert patterns[0]["name"] == "p1"


class TestKnowledgeStoreRebuildIndex:
    """Tests for rebuild_index."""

    def test_rebuild_rules_index(self, tmp_knowledge: Path) -> None:
        """Test rebuilding the rules index."""
        ks = KnowledgeStore(str(tmp_knowledge))
        # Add a rule
        ks.add_rule({"name": "rule1", "tags": ["t1"], "description": "D", "content": "C", "source": "s"})
        # Clear the index manually
        ks._save_index(ks.rules_dir, {"items": []})
        assert len(ks.get_rules()) == 0
        # Rebuild
        ks.rebuild_index("rules")
        rules = ks.get_rules()
        assert len(rules) == 1

    def test_rebuild_patterns_index(self, tmp_knowledge: Path) -> None:
        """Test rebuilding the patterns index."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_pattern({"name": "pat1", "tags": ["t1"], "description": "D", "content": "C", "context": ""})
        ks._save_index(ks.patterns_dir, {"items": []})
        assert len(ks.get_patterns()) == 0
        ks.rebuild_index("patterns")
        patterns = ks.get_patterns()
        assert len(patterns) == 1

    def test_rebuild_invalid_category(self, tmp_knowledge: Path) -> None:
        """Test that invalid category raises ValueError."""
        ks = KnowledgeStore(str(tmp_knowledge))
        with pytest.raises(ValueError, match="Invalid category"):
            ks.rebuild_index("invalid")


class TestSkillComposer:
    """Tests for SkillComposer."""

    def test_compose_valid_skills(self, tmp_knowledge: Path) -> None:
        """Test composing multiple skills."""
        ks = KnowledgeStore(str(tmp_knowledge))
        # Create skill directories with SKILL.md
        skill1_dir = tmp_knowledge.parent / "skills" / "skill1"
        skill1_dir.mkdir(parents=True, exist_ok=True)
        (skill1_dir / "SKILL.md").write_text("# Skill 1 content")

        skill2_dir = tmp_knowledge.parent / "skills" / "skill2"
        skill2_dir.mkdir(parents=True, exist_ok=True)
        (skill2_dir / "SKILL.md").write_text("# Skill 2 content")

        ks.add_skill("skill1", "First skill", path="skill1")
        ks.add_skill("skill2", "Second skill", path="skill2")

        sc = SkillComposer(ks)
        result = sc.compose(["skill1", "skill2"])
        assert "## Skill: skill1" in result
        assert "## Skill: skill2" in result
        assert "# Skill 1 content" in result
        assert "# Skill 2 content" in result

    def test_compose_missing_skill(self, tmp_knowledge: Path) -> None:
        """Test that composing with missing skill raises ValueError."""
        ks = KnowledgeStore(str(tmp_knowledge))
        sc = SkillComposer(ks)
        with pytest.raises(ValueError, match="Composition validation failed"):
            sc.compose(["nonexistent"])

    def test_validate_composition_empty(self, tmp_knowledge: Path) -> None:
        """Test validate_composition with empty list."""
        ks = KnowledgeStore(str(tmp_knowledge))
        sc = SkillComposer(ks)
        issues = sc.validate_composition([])
        assert len(issues) > 0
        assert "No skills specified" in issues[0]

    def test_validate_composition_valid(self, tmp_knowledge: Path) -> None:
        """Test validate_composition with valid skills."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("valid_skill", "A valid skill")
        sc = SkillComposer(ks)
        issues = sc.validate_composition(["valid_skill"])
        assert issues == []

    def test_validate_composition_missing(self, tmp_knowledge: Path) -> None:
        """Test validate_composition with missing skills."""
        ks = KnowledgeStore(str(tmp_knowledge))
        sc = SkillComposer(ks)
        issues = sc.validate_composition(["missing1", "missing2"])
        assert len(issues) == 2

    def test_resolve_order(self, tmp_knowledge: Path) -> None:
        """Test that resolve_order returns as-is."""
        ks = KnowledgeStore(str(tmp_knowledge))
        sc = SkillComposer(ks)
        result = sc.resolve_order(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_get_skill_content(self, tmp_knowledge: Path) -> None:
        """Test getting individual skill content."""
        ks = KnowledgeStore(str(tmp_knowledge))
        skill_dir = tmp_knowledge.parent / "skills" / "test_skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("Test content here")
        ks.add_skill("test_skill", "Test skill", path="test_skill")

        sc = SkillComposer(ks)
        content = sc.get_skill_content("test_skill")
        assert content == "Test content here"

    def test_get_skill_content_not_found(self, tmp_knowledge: Path) -> None:
        """Test getting content for a skill without SKILL.md raises error."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("missing_skill", "Missing", path="missing_path")
        sc = SkillComposer(ks)
        with pytest.raises(FileNotFoundError):
            sc.get_skill_content("missing_skill")


class TestSkillComposerAdvanced:
    """Tests for advanced SkillComposer features: ordering, conflicts, phases, token budget."""

    def test_resolve_order_foundational_first(self, tmp_knowledge: Path) -> None:
        """Skills that are composable_with by many others come first."""
        ks = KnowledgeStore(str(tmp_knowledge))
        # Create skills: C composable_with [A, B], B composable_with [A]
        # A is most foundational (referenced by both B and C)
        # B is next (referenced by C)
        # C is least foundational
        ks.add_skill("skillA", "Foundational skill")
        ks.add_skill("skillB", "Middle skill")
        ks.add_skill("skillC", "Leaf skill")

        # Update index to add composable_with
        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        for item in data["items"]:
            if item["name"] == "skillA":
                item["composable_with"] = []
            elif item["name"] == "skillB":
                item["composable_with"] = ["skillA"]
            elif item["name"] == "skillC":
                item["composable_with"] = ["skillA", "skillB"]
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        result = sc.resolve_order(["skillC", "skillB", "skillA"])
        assert result == ["skillA", "skillB", "skillC"]

    def test_resolve_order_no_composable_data(self, tmp_knowledge: Path) -> None:
        """Skills without composable_with info maintain original order."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("x", "Skill X")
        ks.add_skill("y", "Skill Y")
        ks.add_skill("z", "Skill Z")

        sc = SkillComposer(ks)
        result = sc.resolve_order(["x", "y", "z"])
        assert result == ["x", "y", "z"]

    def test_resolve_order_cycle_graceful(self, tmp_knowledge: Path) -> None:
        """If A composable_with [B] and B composable_with [A], should not crash."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("cycleA", "Cycle A")
        ks.add_skill("cycleB", "Cycle B")

        # Create a cycle: A -> B and B -> A
        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        for item in data["items"]:
            if item["name"] == "cycleA":
                item["composable_with"] = ["cycleB"]
            elif item["name"] == "cycleB":
                item["composable_with"] = ["cycleA"]
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        # Should not crash - returns original order on cycle
        result = sc.resolve_order(["cycleA", "cycleB"])
        assert isinstance(result, list)
        assert set(result) == {"cycleA", "cycleB"}

    def test_detect_conflicts_compatible(self, tmp_knowledge: Path) -> None:
        """Two skills in each other's composable_with produce no warnings."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("comp1", "Compatible 1")
        ks.add_skill("comp2", "Compatible 2")

        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        for item in data["items"]:
            if item["name"] == "comp1":
                item["composable_with"] = ["comp2"]
            elif item["name"] == "comp2":
                item["composable_with"] = ["comp1"]
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        warnings = sc.detect_conflicts(["comp1", "comp2"])
        assert warnings == []

    def test_detect_conflicts_incompatible(self, tmp_knowledge: Path) -> None:
        """Two skills NOT in each other's composable_with produce a warning."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("incompat1", "Incompatible 1")
        ks.add_skill("incompat2", "Incompatible 2")

        # Default composable_with is [] so they are incompatible
        sc = SkillComposer(ks)
        warnings = sc.detect_conflicts(["incompat1", "incompat2"])
        assert len(warnings) == 1
        assert "incompat1" in warnings[0]
        assert "incompat2" in warnings[0]
        assert warnings[0].startswith("Warning:")

    def test_detect_conflicts_mixed(self, tmp_knowledge: Path) -> None:
        """Some compatible pairs, some not."""
        ks = KnowledgeStore(str(tmp_knowledge))
        ks.add_skill("mix1", "Mix 1")
        ks.add_skill("mix2", "Mix 2")
        ks.add_skill("mix3", "Mix 3")

        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        for item in data["items"]:
            if item["name"] == "mix1":
                item["composable_with"] = ["mix2"]  # mix1 compatible with mix2
            elif item["name"] == "mix2":
                item["composable_with"] = []
            elif item["name"] == "mix3":
                item["composable_with"] = []
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        warnings = sc.detect_conflicts(["mix1", "mix2", "mix3"])
        # mix1-mix2: mix1 has mix2 in composable_with -> compatible (one direction is enough)
        # mix1-mix3: neither has the other -> incompatible
        # mix2-mix3: neither has the other -> incompatible
        assert len(warnings) == 2

    def test_compose_for_phase_valid(self, tmp_knowledge: Path) -> None:
        """compose_for_phase with a valid phase returns composed content."""
        ks = KnowledgeStore(str(tmp_knowledge))

        # Create skills with SKILL.md
        skill1_dir = tmp_knowledge.parent / "skills" / "phase_skill1"
        skill1_dir.mkdir(parents=True, exist_ok=True)
        (skill1_dir / "SKILL.md").write_text("Phase skill 1 content")

        skill2_dir = tmp_knowledge.parent / "skills" / "phase_skill2"
        skill2_dir.mkdir(parents=True, exist_ok=True)
        (skill2_dir / "SKILL.md").write_text("Phase skill 2 content")

        ks.add_skill("phase_skill1", "Phase skill 1", path="phase_skill1")
        ks.add_skill("phase_skill2", "Phase skill 2", path="phase_skill2")

        # Write an _index.yaml with workflow section
        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        data["workflow"] = {
            "test_phase": ["phase_skill1", "phase_skill2"],
        }
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        result = sc.compose_for_phase("test_phase")
        assert "Phase skill 1 content" in result
        assert "Phase skill 2 content" in result

    def test_compose_for_phase_invalid(self, tmp_knowledge: Path) -> None:
        """Unknown phase raises ValueError."""
        ks = KnowledgeStore(str(tmp_knowledge))

        # Write an _index.yaml with workflow section
        index_path = tmp_knowledge.parent / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        data["workflow"] = {"existing_phase": ["some_skill"]}
        with open(index_path, "w") as f:
            yaml.safe_dump(data, f)

        sc = SkillComposer(ks)
        with pytest.raises(ValueError, match="Phase 'nonexistent_phase' not found"):
            sc.compose_for_phase("nonexistent_phase")

    def test_token_budget_no_limit(self, tmp_knowledge: Path) -> None:
        """compose with max_tokens=None includes all skills."""
        ks = KnowledgeStore(str(tmp_knowledge))

        skill1_dir = tmp_knowledge.parent / "skills" / "budget1"
        skill1_dir.mkdir(parents=True, exist_ok=True)
        (skill1_dir / "SKILL.md").write_text("Content for budget skill 1")

        skill2_dir = tmp_knowledge.parent / "skills" / "budget2"
        skill2_dir.mkdir(parents=True, exist_ok=True)
        (skill2_dir / "SKILL.md").write_text("Content for budget skill 2")

        ks.add_skill("budget1", "Budget 1", path="budget1")
        ks.add_skill("budget2", "Budget 2", path="budget2")

        sc = SkillComposer(ks)
        result = sc.compose(["budget1", "budget2"], max_tokens=None)
        assert "budget1" in result
        assert "budget2" in result
        assert "[TRUNCATED]" not in result

    def test_token_budget_truncates(self, tmp_knowledge: Path) -> None:
        """compose with very small max_tokens truncates and shows warning."""
        ks = KnowledgeStore(str(tmp_knowledge))

        skill1_dir = tmp_knowledge.parent / "skills" / "trunc1"
        skill1_dir.mkdir(parents=True, exist_ok=True)
        (skill1_dir / "SKILL.md").write_text("Short")

        skill2_dir = tmp_knowledge.parent / "skills" / "trunc2"
        skill2_dir.mkdir(parents=True, exist_ok=True)
        (skill2_dir / "SKILL.md").write_text("A" * 1000)

        ks.add_skill("trunc1", "Truncate 1", path="trunc1")
        ks.add_skill("trunc2", "Truncate 2", path="trunc2")

        sc = SkillComposer(ks)
        # Very small budget - only first skill should fit
        result = sc.compose(["trunc1", "trunc2"], max_tokens=10)
        assert "## Skill: trunc1" in result
        assert "[TRUNCATED]" in result
        assert "trunc2" in result  # mentioned in truncation notice

    def test_validate_composition_with_conflicts(self, tmp_knowledge: Path) -> None:
        """Conflict warnings are returned but compose still works."""
        ks = KnowledgeStore(str(tmp_knowledge))

        skill1_dir = tmp_knowledge.parent / "skills" / "conflict1"
        skill1_dir.mkdir(parents=True, exist_ok=True)
        (skill1_dir / "SKILL.md").write_text("Conflict skill 1")

        skill2_dir = tmp_knowledge.parent / "skills" / "conflict2"
        skill2_dir.mkdir(parents=True, exist_ok=True)
        (skill2_dir / "SKILL.md").write_text("Conflict skill 2")

        ks.add_skill("conflict1", "Conflict 1", path="conflict1")
        ks.add_skill("conflict2", "Conflict 2", path="conflict2")
        # Default composable_with is [], so they are "incompatible"

        sc = SkillComposer(ks)
        issues = sc.validate_composition(["conflict1", "conflict2"])
        # Should have a warning
        assert any("Warning:" in i for i in issues)

        # compose should still work (warnings don't block)
        result = sc.compose(["conflict1", "conflict2"])
        assert "Conflict skill 1" in result
        assert "Conflict skill 2" in result


class TestKnowledgeFiles:
    """Tests for knowledge directory files."""

    def test_rules_index_exists(self, kernel_root: Path) -> None:
        """Test that rules/_index.yaml exists and is valid."""
        path = kernel_root / "knowledge" / "rules" / "_index.yaml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert "items" in data

    def test_skills_index_exists(self, kernel_root: Path) -> None:
        """Test that skills/_index.yaml exists and is valid."""
        path = kernel_root / "skills" / "_index.yaml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        # New format uses core_items and community_items instead of items
        assert "core_items" in data or "items" in data

    def test_patterns_index_exists(self, kernel_root: Path) -> None:
        """Test that patterns/_index.yaml exists and is valid."""
        path = kernel_root / "knowledge" / "patterns" / "_index.yaml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert "items" in data

    def test_rules_manual_dir_exists(self, kernel_root: Path) -> None:
        """Test that rules/manual/ directory exists."""
        assert (kernel_root / "knowledge" / "rules" / "manual").is_dir()

    def test_rules_learned_dir_exists(self, kernel_root: Path) -> None:
        """Test that rules/learned/ directory exists."""
        assert (kernel_root / "knowledge" / "rules" / "learned").is_dir()

    def test_patterns_dir_exists(self, kernel_root: Path) -> None:
        """Test that patterns/ directory exists."""
        assert (kernel_root / "knowledge" / "patterns").is_dir()


class TestSkillPathResolution:
    """Tests for validating that skill paths in _index.yaml resolve correctly."""

    def test_skill_paths_resolve(self, kernel_root: Path) -> None:
        """Test that skill paths in _index.yaml resolve to existing SKILL.md files.

        At least 20 of 29 skills should resolve to actual SKILL.md files.
        Skills with paths that do not resolve are reported as warnings.
        """
        index_path = kernel_root / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        # Support both legacy "items" and new core_items/community_items format
        if "items" in data:
            items = data["items"]
        else:
            items = data.get("core_items", []) + data.get("community_items", [])
        assert len(items) == 29, f"Expected 29 skills in index, found {len(items)}"

        resolved = []
        unresolved = []

        for skill in items:
            name = skill["name"]
            path = skill.get("path", "")

            # Skills are now under skills/{path}/SKILL.md
            skill_md = kernel_root / "skills" / path / "SKILL.md"

            if skill_md.exists():
                resolved.append(name)
            else:
                unresolved.append(name)

        # At least 20 of 29 should resolve
        assert len(resolved) >= 20, (
            f"Only {len(resolved)}/29 skills resolved. "
            f"Unresolved: {unresolved}"
        )

    def test_skill_index_has_required_fields(self, kernel_root: Path) -> None:
        """Test that all skill entries have name, path, and description."""
        index_path = kernel_root / "skills" / "_index.yaml"
        data = yaml.safe_load(index_path.read_text())
        # Support both legacy "items" and new core_items/community_items format
        if "items" in data:
            items = data["items"]
        else:
            items = data.get("core_items", []) + data.get("community_items", [])

        for skill in items:
            assert "name" in skill, f"Skill missing 'name': {skill}"
            assert "path" in skill, f"Skill '{skill.get('name', '?')}' missing 'path'"
            assert "description" in skill, f"Skill '{skill['name']}' missing 'description'"

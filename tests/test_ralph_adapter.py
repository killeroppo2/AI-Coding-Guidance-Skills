"""Tests for the Ralph integration adapter."""

import pytest

from kernel.adapters.ralph_adapter import RalphAdapter


@pytest.fixture
def adapter() -> RalphAdapter:
    """Create a RalphAdapter instance."""
    return RalphAdapter()


@pytest.fixture
def sample_tasks() -> list[dict]:
    """Sample kernel tasks for testing."""
    return [
        {
            "id": "T-001",
            "title": "Set up database schema",
            "description": "Create the initial database tables",
            "status": "done",
            "dependencies": [],
        },
        {
            "id": "T-002",
            "title": "Implement API endpoints",
            "description": "Build REST API endpoints for CRUD operations",
            "status": "pending",
            "dependencies": ["T-001"],
        },
        {
            "id": "T-003",
            "title": "Add authentication",
            "description": "Implement JWT-based auth",
            "status": "pending",
            "dependencies": ["T-001", "T-002"],
        },
    ]


@pytest.fixture
def sample_prd() -> dict:
    """Sample Ralph prd.json data for testing."""
    return {
        "project": "TaskApp",
        "branchName": "ralph/task-status-feature",
        "description": "Add task status tracking",
        "userStories": [
            {
                "id": "US-001",
                "title": "Add status field to tasks table",
                "description": "As a developer, I need to store task status in the database.",
                "acceptanceCriteria": [
                    "Add status column with default 'pending'",
                    "Typecheck passes",
                ],
                "priority": 1,
                "passes": True,
                "notes": "",
            },
            {
                "id": "US-002",
                "title": "Display status badge on task cards",
                "description": "As a user, I want to see task status at a glance.",
                "acceptanceCriteria": [
                    "Each task card shows colored status badge",
                    "Typecheck passes",
                ],
                "priority": 2,
                "passes": False,
                "notes": "",
            },
            {
                "id": "US-003",
                "title": "Add status toggle",
                "description": "As a user, I want to change task status.",
                "acceptanceCriteria": [
                    "Status dropdown exists",
                    "Typecheck passes",
                ],
                "priority": 3,
                "passes": False,
                "notes": "Blocked on US-002",
            },
        ],
    }


class TestExportToPrdJson:
    """Tests for export_to_prd_json method."""

    def test_export_produces_valid_structure(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that export produces all required top-level keys."""
        result = adapter.export_to_prd_json(sample_tasks, "Build a REST API")
        assert "project" in result
        assert "branchName" in result
        assert "description" in result
        assert "userStories" in result

    def test_export_branch_name_kebab_case(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that branchName is correctly kebab-cased."""
        result = adapter.export_to_prd_json(sample_tasks, "Build a REST API")
        assert result["branchName"] == "ralph/build-a-rest-api"

    def test_export_branch_name_special_chars(self, adapter: RalphAdapter) -> None:
        """Test that special characters are removed from branchName."""
        result = adapter.export_to_prd_json([], "Hello! World? (Test) #123")
        assert result["branchName"] == "ralph/hello-world-test-123"

    def test_export_branch_name_underscores(self, adapter: RalphAdapter) -> None:
        """Test that underscores become hyphens in branchName."""
        result = adapter.export_to_prd_json([], "my_cool_project")
        assert result["branchName"] == "ralph/my-cool-project"

    def test_export_description_is_goal(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that description field is the goal text."""
        goal = "Build a REST API"
        result = adapter.export_to_prd_json(sample_tasks, goal)
        assert result["description"] == goal

    def test_export_user_stories_count(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that each task becomes a userStory."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        assert len(result["userStories"]) == 3

    def test_export_user_story_ids_sequential(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that userStory IDs are sequential US-001, US-002, etc."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        ids = [s["id"] for s in result["userStories"]]
        assert ids == ["US-001", "US-002", "US-003"]

    def test_export_maps_title(self, adapter: RalphAdapter, sample_tasks: list[dict]) -> None:
        """Test that task titles are mapped to story titles."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        assert result["userStories"][0]["title"] == "Set up database schema"
        assert result["userStories"][1]["title"] == "Implement API endpoints"

    def test_export_maps_description(self, adapter: RalphAdapter, sample_tasks: list[dict]) -> None:
        """Test that task descriptions are mapped to story descriptions."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        assert result["userStories"][0]["description"] == "Create the initial database tables"

    def test_export_generates_description_when_missing(self, adapter: RalphAdapter) -> None:
        """Test that a default description is generated when task has none."""
        tasks = [{"id": "T-001", "title": "Fix the bug", "status": "pending"}]
        result = adapter.export_to_prd_json(tasks, "goal")
        assert result["userStories"][0]["description"] == "As a developer, I want Fix the bug"

    def test_export_maps_status_to_passes(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that done status maps to passes=True."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        assert result["userStories"][0]["passes"] is True  # status=done
        assert result["userStories"][1]["passes"] is False  # status=pending
        assert result["userStories"][2]["passes"] is False  # status=pending

    def test_export_priority_sequential(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that priority is assigned sequentially starting at 1."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        priorities = [s["priority"] for s in result["userStories"]]
        assert priorities == [1, 2, 3]

    def test_export_stories_have_all_required_keys(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that each story has all required Ralph prd.json keys."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        required_keys = {
            "id",
            "title",
            "description",
            "acceptanceCriteria",
            "priority",
            "passes",
            "notes",
        }
        for story in result["userStories"]:
            assert set(story.keys()) == required_keys

    def test_export_notes_empty(self, adapter: RalphAdapter, sample_tasks: list[dict]) -> None:
        """Test that notes field is always empty string on export."""
        result = adapter.export_to_prd_json(sample_tasks, "goal")
        for story in result["userStories"]:
            assert story["notes"] == ""

    def test_export_empty_tasks(self, adapter: RalphAdapter) -> None:
        """Test export with an empty tasks list."""
        result = adapter.export_to_prd_json([], "Build something")
        assert result["userStories"] == []
        assert result["description"] == "Build something"
        assert result["branchName"] == "ralph/build-something"

    def test_export_acceptance_criteria_default(self, adapter: RalphAdapter) -> None:
        """Test that default acceptance criteria are generated."""
        tasks = [{"id": "T-001", "title": "Do thing", "status": "pending"}]
        result = adapter.export_to_prd_json(tasks, "goal")
        criteria = result["userStories"][0]["acceptanceCriteria"]
        assert "Typecheck passes" in criteria
        assert len(criteria) >= 1

    def test_export_acceptance_criteria_preserved(self, adapter: RalphAdapter) -> None:
        """Test that existing acceptance criteria are preserved."""
        tasks = [
            {
                "id": "T-001",
                "title": "Do thing",
                "status": "pending",
                "acceptance_criteria": ["Tests pass", "Docs updated"],
            }
        ]
        result = adapter.export_to_prd_json(tasks, "goal")
        criteria = result["userStories"][0]["acceptanceCriteria"]
        assert "Tests pass" in criteria
        assert "Docs updated" in criteria
        assert "Typecheck passes" in criteria

    def test_export_acceptance_criteria_no_duplicate_typecheck(self, adapter: RalphAdapter) -> None:
        """Test that Typecheck passes is not duplicated if already present."""
        tasks = [
            {
                "id": "T-001",
                "title": "Do thing",
                "status": "pending",
                "acceptance_criteria": ["Typecheck passes", "Tests pass"],
            }
        ]
        result = adapter.export_to_prd_json(tasks, "goal")
        criteria = result["userStories"][0]["acceptanceCriteria"]
        assert criteria.count("Typecheck passes") == 1


class TestImportFromPrdJson:
    """Tests for import_from_prd_json method."""

    def test_import_converts_stories_to_tasks(
        self, adapter: RalphAdapter, sample_prd: dict
    ) -> None:
        """Test that userStories become kernel tasks."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert len(tasks) == 3

    def test_import_task_ids_sequential(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that imported tasks have sequential T-001 IDs."""
        tasks = adapter.import_from_prd_json(sample_prd)
        ids = [t["id"] for t in tasks]
        assert ids == ["T-001", "T-002", "T-003"]

    def test_import_maps_title(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that story titles are mapped to task titles."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert tasks[0]["title"] == "Add status field to tasks table"
        assert tasks[1]["title"] == "Display status badge on task cards"

    def test_import_maps_description(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that story descriptions are mapped to task descriptions."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert (
            tasks[0]["description"]
            == "As a developer, I need to store task status in the database."
        )

    def test_import_status_from_passes_true(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that passes=True maps to status=done."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert tasks[0]["status"] == "done"

    def test_import_status_from_passes_false(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that passes=False maps to status=pending."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert tasks[1]["status"] == "pending"
        assert tasks[2]["status"] == "pending"

    def test_import_dependency_chain(self, adapter: RalphAdapter, sample_prd: dict) -> None:
        """Test that dependency chain is created based on priority ordering."""
        tasks = adapter.import_from_prd_json(sample_prd)
        assert tasks[0]["dependencies"] == []  # priority 1, no deps
        assert tasks[1]["dependencies"] == ["T-001"]  # priority 2, depends on T-001
        assert tasks[2]["dependencies"] == ["T-002"]  # priority 3, depends on T-002

    def test_import_empty_user_stories(self, adapter: RalphAdapter) -> None:
        """Test import with empty userStories list."""
        prd = {
            "project": "Test",
            "branchName": "ralph/test",
            "description": "Test",
            "userStories": [],
        }
        tasks = adapter.import_from_prd_json(prd)
        assert tasks == []

    def test_import_missing_user_stories_key(self, adapter: RalphAdapter) -> None:
        """Test import when userStories key is missing."""
        prd = {"project": "Test", "branchName": "ralph/test", "description": "Test"}
        tasks = adapter.import_from_prd_json(prd)
        assert tasks == []

    def test_import_handles_missing_title(self, adapter: RalphAdapter) -> None:
        """Test import when story title is missing."""
        prd = {
            "userStories": [{"id": "US-001", "priority": 1, "passes": False, "description": "desc"}]
        }
        tasks = adapter.import_from_prd_json(prd)
        assert tasks[0]["title"] == ""

    def test_import_handles_missing_description(self, adapter: RalphAdapter) -> None:
        """Test import when story description is missing."""
        prd = {"userStories": [{"id": "US-001", "title": "Test", "priority": 1, "passes": False}]}
        tasks = adapter.import_from_prd_json(prd)
        assert tasks[0]["description"] == ""

    def test_import_handles_missing_passes(self, adapter: RalphAdapter) -> None:
        """Test import when passes field is missing defaults to pending."""
        prd = {"userStories": [{"id": "US-001", "title": "Test", "priority": 1}]}
        tasks = adapter.import_from_prd_json(prd)
        assert tasks[0]["status"] == "pending"

    def test_import_sorts_by_priority(self, adapter: RalphAdapter) -> None:
        """Test that import sorts stories by priority before assigning IDs."""
        prd = {
            "userStories": [
                {"id": "US-003", "title": "Third", "priority": 3, "passes": False},
                {"id": "US-001", "title": "First", "priority": 1, "passes": True},
                {"id": "US-002", "title": "Second", "priority": 2, "passes": False},
            ]
        }
        tasks = adapter.import_from_prd_json(prd)
        assert tasks[0]["title"] == "First"
        assert tasks[1]["title"] == "Second"
        assert tasks[2]["title"] == "Third"

    def test_import_same_priority_parallel(self, adapter: RalphAdapter) -> None:
        """Test that stories with same priority are treated as parallel (no dependency between them)."""
        prd = {
            "userStories": [
                {"id": "US-001", "title": "Setup", "priority": 1, "passes": True},
                {"id": "US-002", "title": "Feature A", "priority": 2, "passes": False},
                {"id": "US-003", "title": "Feature B", "priority": 2, "passes": False},
                {"id": "US-004", "title": "Integration", "priority": 3, "passes": False},
            ]
        }
        tasks = adapter.import_from_prd_json(prd)
        # Priority 1: no deps
        assert tasks[0]["dependencies"] == []
        # Priority 2 stories: both depend on the last priority-1 task (T-001), not on each other
        assert tasks[1]["dependencies"] == ["T-001"]
        assert tasks[2]["dependencies"] == ["T-001"]
        # Priority 3: depends on the last priority-2 task (T-003)
        assert tasks[3]["dependencies"] == ["T-003"]


class TestRoundTrip:
    """Tests for export then import round-trip consistency."""

    def test_round_trip_preserves_titles(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that exporting then importing preserves task titles."""
        prd = adapter.export_to_prd_json(sample_tasks, "Build API")
        imported = adapter.import_from_prd_json(prd)
        for orig, imported_task in zip(sample_tasks, imported):
            assert orig["title"] == imported_task["title"]

    def test_round_trip_preserves_descriptions(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that exporting then importing preserves descriptions."""
        prd = adapter.export_to_prd_json(sample_tasks, "Build API")
        imported = adapter.import_from_prd_json(prd)
        for orig, imported_task in zip(sample_tasks, imported):
            assert orig["description"] == imported_task["description"]

    def test_round_trip_preserves_status(
        self, adapter: RalphAdapter, sample_tasks: list[dict]
    ) -> None:
        """Test that exporting then importing preserves done/pending status."""
        prd = adapter.export_to_prd_json(sample_tasks, "Build API")
        imported = adapter.import_from_prd_json(prd)
        for orig, imported_task in zip(sample_tasks, imported):
            if orig["status"] == "done":
                assert imported_task["status"] == "done"
            else:
                assert imported_task["status"] == "pending"

    def test_round_trip_empty_tasks(self, adapter: RalphAdapter) -> None:
        """Test round-trip with empty tasks list."""
        prd = adapter.export_to_prd_json([], "Empty project")
        imported = adapter.import_from_prd_json(prd)
        assert imported == []


class TestEdgeCases:
    """Tests for edge cases and special characters."""

    def test_export_goal_with_unicode(self, adapter: RalphAdapter) -> None:
        """Test export handles unicode in goal."""
        result = adapter.export_to_prd_json([], "Build cafe app")
        assert "ralph/" in result["branchName"]

    def test_export_very_long_goal(self, adapter: RalphAdapter) -> None:
        """Test that very long goals are truncated in branchName."""
        long_goal = "a" * 200
        result = adapter.export_to_prd_json([], long_goal)
        # branchName should be truncated (50 chars max in kebab + ralph/ prefix)
        assert len(result["branchName"]) <= 56  # "ralph/" (6) + 50

    def test_export_goal_only_special_chars(self, adapter: RalphAdapter) -> None:
        """Test export with goal that is all special characters."""
        result = adapter.export_to_prd_json([], "!@#$%^&*()")
        assert result["branchName"] == "ralph/"

    def test_export_task_missing_all_fields(self, adapter: RalphAdapter) -> None:
        """Test export with task dict missing all fields."""
        tasks = [{}]
        result = adapter.export_to_prd_json(tasks, "goal")
        story = result["userStories"][0]
        assert story["title"] == ""
        assert story["passes"] is False
        assert story["priority"] == 1

    def test_import_single_story_no_dependencies(self, adapter: RalphAdapter) -> None:
        """Test that a single story with priority 1 has no dependencies."""
        prd = {
            "userStories": [{"id": "US-001", "title": "Only one", "priority": 1, "passes": False}]
        }
        tasks = adapter.import_from_prd_json(prd)
        assert tasks[0]["dependencies"] == []

    def test_export_project_name_derived(self, adapter: RalphAdapter) -> None:
        """Test that project name is derived from goal words."""
        result = adapter.export_to_prd_json([], "Build a REST API service")
        # Should pick meaningful words (>2 chars), capitalize them
        assert result["project"] != ""
        assert result["project"][0].isupper()

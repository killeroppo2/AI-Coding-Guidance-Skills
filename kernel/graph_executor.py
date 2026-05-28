"""Graph executor for the kernel workflow.

This module handles loading, navigating, and modifying the kernel's
workflow graph defined in graph.yaml.
"""

from pathlib import Path

import yaml


class GraphExecutor:
    """Executes and manages the kernel workflow graph.

    The graph defines nodes (workflow steps) and transitions between them.
    Each node has a prompt file and possible transitions based on conditions.
    """

    def __init__(self, graph_path: str) -> None:
        """Initialize the graph executor.

        Args:
            graph_path: Path to the graph.yaml file.
        """
        self.graph_path = Path(graph_path)
        self.graph = self.load_graph()

    def load_graph(self) -> dict:
        """Load graph YAML and validate structure.

        Returns:
            The parsed graph dict.

        Raises:
            FileNotFoundError: If graph_path does not exist.
            ValueError: If graph structure is invalid.
        """
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_path}")
        with open(self.graph_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "nodes" not in data or not isinstance(data["nodes"], list):
            raise ValueError("Graph must contain a 'nodes' list")
        return data

    def get_current_node(self, state: dict | None = None) -> dict:
        """Given state with current_node field, return that node's definition.

        Args:
            state: State dict with 'current_node' field. If None, uses default_start.

        Returns:
            The node dict for the current node.

        Raises:
            KeyError: If the node is not found in the graph.
        """
        if state is None:
            node_id = self.graph.get("default_start", "init")
        else:
            node_id = state.get("current_node", self.graph.get("default_start", "init"))
        return self.get_node(node_id)

    def get_node(self, node_id: str) -> dict:
        """Get a specific node by ID.

        Args:
            node_id: The identifier of the node.

        Returns:
            The node dict.

        Raises:
            KeyError: If the node is not found.
        """
        for node in self.graph.get("nodes", []):
            if node.get("id") == node_id:
                return dict(node)
        raise KeyError(f"Node not found: {node_id}")

    def get_prompt_for_node(self, node_id: str) -> str:
        """Return path to the node's prompt file.

        Args:
            node_id: The node identifier.

        Returns:
            The path string to the prompt file (relative as stored in graph).
        """
        node = self.get_node(node_id)
        prompt_file: str = node.get("prompt_file", "")
        return prompt_file

    def advance(self, current_node_id: str, condition: str) -> str:
        """Given current node and a condition, return the next node_id.

        Args:
            current_node_id: The current node's ID.
            condition: The condition string to match against transitions.

        Returns:
            The next node ID.

        Raises:
            KeyError: If current node is not found.
            ValueError: If no matching transition is found for the condition.
        """
        node = self.get_node(current_node_id)
        transitions = node.get("transitions", [])
        for transition in transitions:
            if transition.get("condition") == condition:
                next_id: str = transition["to"]
                return next_id
        raise ValueError(
            f"No transition from '{current_node_id}' with condition '{condition}'"
        )

    def get_available_transitions(self, node_id: str) -> list:
        """Return list of transitions from a node.

        Args:
            node_id: The node identifier.

        Returns:
            List of transition dicts.
        """
        node = self.get_node(node_id)
        transitions: list = node.get("transitions", [])
        return transitions

    def validate_graph(self) -> tuple[bool, list]:
        """Check graph is valid.

        Validates that all transitions point to existing nodes and that
        there are no orphan nodes (unreachable from default_start).
        Also detects deterministic loops in Mode 1 path (following first
        transitions only) and reports them as warnings.

        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        issues = []
        node_ids = {node["id"] for node in self.graph.get("nodes", [])}

        # Check default_start exists
        default_start = self.graph.get("default_start", "init")
        if default_start not in node_ids:
            issues.append(f"default_start '{default_start}' not found in nodes")

        # Check all transitions point to existing nodes
        for node in self.graph.get("nodes", []):
            for transition in node.get("transitions", []):
                target = transition.get("to")
                if target not in node_ids:
                    issues.append(
                        f"Node '{node['id']}' has transition to unknown node '{target}'"
                    )

        # Check for orphan nodes (unreachable)
        reachable = set()
        queue = [default_start]
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            if current not in node_ids:
                continue
            try:
                node = self.get_node(current)
                for transition in node.get("transitions", []):
                    target = transition.get("to")
                    if target not in reachable:
                        queue.append(target)
            except KeyError:
                pass

        orphans = node_ids - reachable
        for orphan in orphans:
            issues.append(f"Node '{orphan}' is unreachable from '{default_start}'")

        # Detect deterministic loops (Mode 1 path following first transitions)
        loop_warning = self._detect_first_transition_loop(default_start, node_ids)
        if loop_warning:
            issues.append(loop_warning)

        # Loop warnings do not make the graph invalid
        hard_errors = [
            i for i in issues
            if not i.startswith("Warning:")
        ]
        return (len(hard_errors) == 0, issues)

    def _detect_first_transition_loop(self, start: str, node_ids: set) -> str | None:
        """Detect if following only first transitions creates a cycle.

        This is the exact path Mode 1 takes. If a cycle is found, returns
        a warning string. Otherwise returns None.

        Args:
            start: The starting node ID.
            node_ids: Set of all valid node IDs.

        Returns:
            Warning string if loop detected, None otherwise.
        """
        visited = []
        visited_set = set()
        current = start

        while current and current in node_ids and current not in visited_set:
            visited.append(current)
            visited_set.add(current)
            try:
                node = self.get_node(current)
            except KeyError:
                break
            transitions = node.get("transitions", [])
            if not transitions:
                # Terminal node - no loop
                return None
            current = transitions[0].get("to")

        if current in visited_set:
            # Build the path showing the loop
            loop_start_idx = visited.index(current)
            path = visited[loop_start_idx:] + [current]
            path_str = " -> ".join(path)
            return (
                f"Warning: Deterministic loop detected in Mode 1 path: "
                f"{path_str} (following first transitions only)"
            )
        return None

    def add_node(self, node_dict: dict) -> None:
        """Add a new node to the graph.

        Args:
            node_dict: The node definition dict with at least 'id' field.

        Raises:
            ValueError: If node with same ID already exists or dict is invalid.
        """
        if "id" not in node_dict:
            raise ValueError("Node dict must have an 'id' field")
        node_ids = {node["id"] for node in self.graph.get("nodes", [])}
        if node_dict["id"] in node_ids:
            raise ValueError(f"Node '{node_dict['id']}' already exists")
        # Ensure required fields have defaults
        node_dict.setdefault("transitions", [])
        node_dict.setdefault("max_retries", 1)
        node_dict.setdefault("prompt_file", "")
        node_dict.setdefault("description", "")
        self.graph["nodes"].append(node_dict)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the graph.

        Fails if other nodes transition to it.

        Args:
            node_id: The ID of the node to remove.

        Raises:
            KeyError: If node does not exist.
            ValueError: If other nodes still reference this node.
        """
        # Verify node exists
        self.get_node(node_id)

        # Check if other nodes transition to this one
        for node in self.graph.get("nodes", []):
            if node["id"] == node_id:
                continue
            for transition in node.get("transitions", []):
                if transition.get("to") == node_id:
                    raise ValueError(
                        f"Cannot remove '{node_id}': node '{node['id']}' "
                        f"has a transition to it"
                    )

        # Remove the node
        self.graph["nodes"] = [
            n for n in self.graph["nodes"] if n["id"] != node_id
        ]

    def save_graph(self) -> None:
        """Write current graph back to YAML file."""
        with open(self.graph_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.graph, f, default_flow_style=False, allow_unicode=True)

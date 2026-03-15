"""Formula syntax validation and cell reference extraction for sheet tabs."""

import re
from typing import Dict, List, Set, Tuple

from core.schemas.studio_schema import SheetTab

# Match cell references like A1, B10, AA100, AB2.
# Lookbehind excludes mid-word matches (e.g. tail of XLOG10);
# lookahead rejects both trailing digits (forces consuming all digits)
# and open-parens (excludes function calls like LOG10( or ATAN2().
_CELL_REF_PATTERN = re.compile(r"(?<![A-Z])[A-Z]{1,3}[0-9]+(?![0-9(])")
# Match a single cell ref for parsing
_SINGLE_REF = re.compile(r"^([A-Z]{1,3})([0-9]+)$")


def _col_letter_to_index(letters: str) -> int:
    """Convert column letters to 1-based index. A=1, B=2, ..., Z=26, AA=27."""
    result = 0
    for ch in letters:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result


def validate_formula_syntax(formula: str) -> bool:
    """Check that formula starts with '=' and has balanced parentheses."""
    if not formula or not formula.startswith("="):
        return False
    depth = 0
    for ch in formula:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def extract_cell_refs(formula: str) -> List[str]:
    """Extract all cell references (e.g., 'A1', 'B2', 'C10') from a formula.

    For ranges like A1:B10, both endpoints are extracted.
    """
    return _CELL_REF_PATTERN.findall(formula)


def _parse_cell_ref(ref: str) -> Tuple[int, int]:
    """Parse a cell reference into (row, col) 1-based indices.

    Returns (0, 0) if the reference cannot be parsed.
    """
    m = _SINGLE_REF.match(ref)
    if not m:
        return (0, 0)
    col = _col_letter_to_index(m.group(1))
    row = int(m.group(2))
    return (row, col)


def validate_formula_refs(formula: str, max_row: int, max_col: int) -> bool:
    """Check that all cell refs in the formula point to valid in-tab coordinates.

    max_row and max_col are 1-based upper bounds (inclusive).
    """
    refs = extract_cell_refs(formula)
    if not refs:
        return True  # No refs to validate
    for ref in refs:
        row, col = _parse_cell_ref(ref)
        if row == 0 or col == 0:
            return False
        if row > max_row or col > max_col:
            return False
    return True


def detect_circular_refs(formulas: Dict[str, str]) -> List[str]:
    """Detect cells participating in circular references.

    Builds a directed dependency graph (formula cell → referenced formula cells)
    and finds all cells that lie on a cycle using DFS.

    Returns a sorted list of cell addresses that are members of cycles.
    Cells that merely lead into a cycle are NOT included.
    """
    if not formulas:
        return []

    formula_cells: Set[str] = set(formulas.keys())

    # Build adjacency list: cell -> set of formula cells it references
    graph: Dict[str, Set[str]] = {}
    for cell, formula in formulas.items():
        refs = extract_cell_refs(formula)
        # Only include edges to other formula cells (data cells can't create cycles)
        graph[cell] = {ref for ref in refs if ref in formula_cells}

    # DFS cycle detection: find all cells on cycles
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {cell: WHITE for cell in formula_cells}
    on_cycle: Set[str] = set()

    def dfs(node: str, path: List[str]) -> bool:
        """Returns True if node leads to (or is on) a cycle."""
        color[node] = GRAY
        path.append(node)
        found_cycle = False
        for neighbor in graph.get(node, set()):
            if color[neighbor] == GRAY:
                # Back edge: mark all nodes on the cycle
                cycle_start = path.index(neighbor)
                on_cycle.update(path[cycle_start:])
                found_cycle = True
            elif color[neighbor] == WHITE:
                if dfs(neighbor, path):
                    found_cycle = True
        path.pop()
        color[node] = BLACK
        return found_cycle

    for cell in formula_cells:
        if color[cell] == WHITE:
            dfs(cell, [])

    return sorted(on_cycle)


def validate_tab_formulas(tab: SheetTab) -> List[str]:
    """Validate all formulas in a tab. Returns list of warning messages for invalid formulas.

    - Formula references must point to cells within data bounds
    - Formula keys may extend up to one column/row beyond bounds (for totals)
    - Invalid formulas are removed from tab.formulas
    """
    if not tab.formulas:
        return []

    warnings = []
    # max_row = header row (1) + data rows
    max_row = len(tab.rows) + 1
    max_col = len(tab.headers)

    # Keys can extend one beyond for derived columns/totals rows
    max_key_row = max_row + 1
    max_key_col = max_col + 1

    to_remove = []
    for cell_addr, formula in tab.formulas.items():
        # Validate formula syntax
        if not validate_formula_syntax(formula):
            warnings.append(f"Removed invalid formula at {cell_addr}: invalid syntax")
            to_remove.append(cell_addr)
            continue

        # Validate formula key position
        key_row, key_col = _parse_cell_ref(cell_addr)
        if key_row == 0 or key_col == 0:
            warnings.append(
                f"Removed invalid formula at {cell_addr}: invalid cell address"
            )
            to_remove.append(cell_addr)
            continue
        if key_row > max_key_row or key_col > max_key_col:
            warnings.append(
                f"Removed invalid formula at {cell_addr}: key position out of bounds"
            )
            to_remove.append(cell_addr)
            continue

        # Validate formula references (must be within data bounds)
        if not validate_formula_refs(formula, max_row, max_col):
            warnings.append(
                f"Removed invalid formula at {cell_addr}: reference out of bounds"
            )
            to_remove.append(cell_addr)
            continue

    for key in to_remove:
        del tab.formulas[key]

    # Detect circular references among remaining (valid) formulas
    circular_cells = detect_circular_refs(tab.formulas)
    for cell_addr in circular_cells:
        warnings.append(
            f"Removed invalid formula at {cell_addr}: circular reference detected"
        )
        del tab.formulas[cell_addr]

    return warnings

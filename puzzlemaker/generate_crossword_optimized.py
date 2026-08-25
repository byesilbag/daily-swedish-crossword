#!/usr/bin/env python3
"""
Optimized Crossword Generator

Uses an efficient constraint satisfaction approach with:
- Arc Consistency (AC-3) for initial domain reduction
- Most Constrained Variable (MCV) heuristic for variable ordering
- Forward Checking with constraint propagation
- Pattern-based candidate filtering using trie-like indexing

Usage:
    python generate_crossword_optimized.py --input example.xml --clues clues.csv --output output.xml
"""

import argparse
import csv
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple


class CrosswordGenerator:
    """Optimized crossword generator using CSP techniques."""

    def __init__(self, clues_file: str, verbose: bool = False):
        self.verbose = verbose
        self.words_by_length: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        self.word_set: Set[str] = set()
        
        # Pattern index: (length, position, char) -> set of words
        self.pattern_index: Dict[Tuple[int, int, str], Set[str]] = defaultdict(set)
        
        self._load_clues(clues_file)
        self._build_pattern_index()

    def _load_clues(self, filename: str) -> None:
        """Load clues from CSV file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        word = row[0].strip().upper()
                        clue = row[1].strip()
                        if word and clue:
                            self.words_by_length[len(word)].append((word, clue))
                            self.word_set.add(word)
        except FileNotFoundError:
            print(f"Error: Clues file '{filename}' not found.")
            sys.exit(1)

        if self.verbose:
            print(f"Loaded {len(self.word_set)} unique words")
            print(f"Lengths available: {sorted(self.words_by_length.keys())}")

    def _build_pattern_index(self) -> None:
        """Build pattern index for fast candidate lookup."""
        for length, words in self.words_by_length.items():
            for word, _ in words:
                for pos, char in enumerate(word):
                    self.pattern_index[(length, pos, char)].add(word)

    def get_candidates(self, length: int, constraints: Dict[int, str]) -> List[str]:
        """
        Get candidate words matching given length and position constraints.
        Uses pattern index for efficient filtering.
        """
        if length not in self.words_by_length:
            return []

        if not constraints:
            return [w for w, _ in self.words_by_length[length]]

        # Start with candidates matching first constraint
        first_pos, first_char = next(iter(constraints.items()))
        candidates = self.pattern_index.get((length, first_pos, first_char), set()).copy()

        # Intersect with other constraints
        for pos, char in constraints.items():
            if pos == first_pos:
                continue
            matching = self.pattern_index.get((length, pos, char), set())
            candidates &= matching
            if not candidates:
                return []

        return list(candidates)

    def get_clue_for_word(self, word: str) -> Optional[str]:
        """Get clue for a word."""
        length = len(word)
        for w, clue in self.words_by_length.get(length, []):
            if w == word:
                return clue
        return None


class PuzzleParser:
    """Parse crossword puzzle XML structure."""

    def __init__(self, xml_file: str):
        self.xml_file = xml_file
        self.tree = None
        self.root = None
        self.crossword = None
        self.grid = None
        self.width = 0
        self.height = 0
        self.words_info: Dict[str, dict] = {}
        self.grid_map: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        self.intersections: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(dict)

        self._parse()

    def _parse(self) -> None:
        """Parse the XML file."""
        try:
            self.tree = ET.parse(self.xml_file)
            self.root = self.tree.getroot()
        except Exception as e:
            print(f"Error parsing XML: {e}")
            sys.exit(1)

        # Find crossword element (handle namespaces)
        self.crossword = self._find_element('crossword')
        if self.crossword is None:
            print("Could not find crossword element")
            sys.exit(1)

        # Find grid element
        self.grid = self._find_element('grid', self.crossword)
        if self.grid is not None:
            self.width = int(self.grid.get('width', 0))
            self.height = int(self.grid.get('height', 0))

        self._parse_words()
        self._calculate_intersections()

    def _find_element(self, tag_name: str, parent: Optional[ET.Element] = None) -> Optional[ET.Element]:
        """Find element handling namespaces."""
        search_in = parent if parent is not None else self.root
        
        # Direct search
        elem = search_in.find(tag_name)
        if elem is not None:
            return elem

        # Search with namespace
        for child in search_in.iter():
            if child.tag.endswith(tag_name):
                return child

        return None

    def _parse_words(self) -> None:
        """Parse word elements from crossword."""
        for elem in self.crossword.iter():
            if elem.tag.endswith('word'):
                wid = elem.get('id')
                x_attr = elem.get('x')
                y_attr = elem.get('y')

                if not all([wid, x_attr, y_attr]):
                    continue

                coords = []
                direction = None

                if '-' in str(x_attr):
                    # Horizontal word
                    start_x, end_x = map(int, x_attr.split('-'))
                    y = int(y_attr)
                    coords = [(x, y) for x in range(start_x, end_x + 1)]
                    direction = 'horizontal'
                elif '-' in str(y_attr):
                    # Vertical word
                    start_y, end_y = map(int, y_attr.split('-'))
                    x = int(x_attr)
                    coords = [(x, y) for y in range(start_y, end_y + 1)]
                    direction = 'vertical'
                else:
                    # Single cell
                    coords = [(int(x_attr), int(y_attr))]
                    direction = 'single'

                self.words_info[wid] = {
                    'length': len(coords),
                    'coords': coords,
                    'direction': direction,
                    'element': elem
                }

                for coord in coords:
                    self.grid_map[coord].append(wid)

    def _calculate_intersections(self) -> None:
        """Calculate intersections between words."""
        for wid, info in self.words_info.items():
            for i, coord in enumerate(info['coords']):
                for other_wid in self.grid_map[coord]:
                    if other_wid != wid:
                        other_info = self.words_info[other_wid]
                        other_pos = other_info['coords'].index(coord)
                        
                        if other_wid not in self.intersections[wid]:
                            self.intersections[wid][other_wid] = []
                        self.intersections[wid][other_wid].append((i, other_pos))


class CSPSolver:
    """Constraint Satisfaction Problem solver for crossword."""

    def __init__(self, generator: CrosswordGenerator, parser: PuzzleParser, verbose: bool = False):
        self.generator = generator
        self.parser = parser
        self.verbose = verbose
        
        # Domain for each word slot
        self.domains: Dict[str, Set[str]] = {}
        
        # Current assignment
        self.assignment: Dict[str, str] = {}
        
        # Statistics
        self.backtracks = 0
        self.nodes_explored = 0

    def solve(self) -> Optional[Dict[str, Tuple[str, str]]]:
        """Main solving method."""
        start_time = time.time()

        # Initialize domains
        self._initialize_domains()
        
        if self.verbose:
            print(f"Initial domains: {[(wid, len(d)) for wid, d in self.domains.items()]}")

        # Apply AC-3 for initial constraint propagation
        if not self._ac3():
            print("No solution possible after AC-3")
            return None

        if self.verbose:
            print(f"After AC-3: {[(wid, len(d)) for wid, d in self.domains.items()]}")

        # Check for empty domains
        for wid, domain in self.domains.items():
            if not domain:
                print(f"Empty domain for word {wid} (length {self.parser.words_info[wid]['length']})")
                return None

        # Solve using backtracking with forward checking
        result = self._backtrack()

        elapsed = time.time() - start_time
        if self.verbose:
            print(f"Solved in {elapsed:.2f}s")
            print(f"Nodes explored: {self.nodes_explored}")
            print(f"Backtracks: {self.backtracks}")

        if result:
            # Convert to (word, clue) format
            solution = {}
            for wid, word in self.assignment.items():
                clue = self.generator.get_clue_for_word(word)
                solution[wid] = (word, clue or "")
            return solution

        return None

    def _initialize_domains(self) -> None:
        """Initialize domains for each word slot."""
        for wid, info in self.parser.words_info.items():
            length = info['length']
            candidates = self.generator.get_candidates(length, {})
            self.domains[wid] = set(candidates)

    def _ac3(self) -> bool:
        """
        AC-3 algorithm for arc consistency.
        Reduces domains by removing values that can't be part of any solution.
        """
        # Build queue of all arcs
        queue = []
        for wid in self.parser.words_info:
            for other_wid in self.parser.intersections.get(wid, {}):
                queue.append((wid, other_wid))

        while queue:
            xi, xj = queue.pop(0)
            if self._revise(xi, xj):
                if not self.domains[xi]:
                    return False
                # Add arcs from neighbors back to xi
                for xk in self.parser.intersections.get(xi, {}):
                    if xk != xj:
                        queue.append((xk, xi))

        return True

    def _revise(self, xi: str, xj: str) -> bool:
        """Revise domain of xi based on constraint with xj."""
        revised = False
        intersections = self.parser.intersections.get(xi, {}).get(xj, [])
        
        if not intersections:
            return False

        to_remove = set()
        for word_i in self.domains[xi]:
            # Check if there exists any word in xj's domain that's compatible
            has_support = False
            for pos_i, pos_j in intersections:
                char_i = word_i[pos_i]
                for word_j in self.domains[xj]:
                    if word_j[pos_j] == char_i and word_i != word_j:
                        has_support = True
                        break
                if has_support:
                    break

            if not has_support:
                to_remove.add(word_i)
                revised = True

        self.domains[xi] -= to_remove
        return revised

    def _select_unassigned_variable(self) -> Optional[str]:
        """
        Select next variable using MCV (Most Constrained Variable) heuristic.
        Returns the word slot with fewest remaining candidates.
        """
        unassigned = [wid for wid in self.parser.words_info if wid not in self.assignment]
        
        if not unassigned:
            return None

        # MCV: choose variable with smallest domain
        # Tie-breaker: choose variable with most constraints (most intersections)
        return min(unassigned, key=lambda wid: (
            len(self.domains[wid]),
            -len(self.parser.intersections.get(wid, {}))
        ))

    def _order_domain_values(self, wid: str) -> List[str]:
        """
        Order domain values using LCV (Least Constraining Value) heuristic.
        Returns values that rule out the fewest choices for neighbors.
        """
        domain = list(self.domains[wid])
        
        if len(domain) <= 1:
            return domain

        # For efficiency, only compute LCV scores if domain is small enough
        if len(domain) > 100:
            return domain

        def count_eliminations(word: str) -> int:
            """Count how many values this word eliminates from neighbors."""
            count = 0
            for other_wid, intersections in self.parser.intersections.get(wid, {}).items():
                if other_wid in self.assignment:
                    continue
                for pos_i, pos_j in intersections:
                    char = word[pos_i]
                    for other_word in self.domains[other_wid]:
                        if other_word[pos_j] != char:
                            count += 1
            return count

        return sorted(domain, key=count_eliminations)

    def _is_consistent(self, wid: str, word: str) -> bool:
        """Check if assigning word to wid is consistent with current assignment."""
        # Check that word isn't already used
        if word in self.assignment.values():
            return False

        # Check all intersections with assigned words
        for other_wid, intersections in self.parser.intersections.get(wid, {}).items():
            if other_wid in self.assignment:
                other_word = self.assignment[other_wid]
                for pos_i, pos_j in intersections:
                    if word[pos_i] != other_word[pos_j]:
                        return False

        return True

    def _forward_check(self, wid: str, word: str) -> Optional[Dict[str, Set[str]]]:
        """
        Forward checking: reduce domains of unassigned neighbors.
        Returns pruned values (for restoration on backtrack) or None if any domain becomes empty.
        """
        pruned: Dict[str, Set[str]] = defaultdict(set)

        for other_wid, intersections in self.parser.intersections.get(wid, {}).items():
            if other_wid in self.assignment:
                continue

            for pos_i, pos_j in intersections:
                required_char = word[pos_i]
                to_remove = set()
                
                for other_word in self.domains[other_wid]:
                    if other_word[pos_j] != required_char or other_word == word:
                        to_remove.add(other_word)

                self.domains[other_wid] -= to_remove
                pruned[other_wid] |= to_remove

                if not self.domains[other_wid]:
                    # Restore pruned values
                    for restore_wid, restore_words in pruned.items():
                        self.domains[restore_wid] |= restore_words
                    return None

        return pruned

    def _backtrack(self) -> bool:
        """Backtracking search with forward checking."""
        self.nodes_explored += 1

        # Check if complete
        if len(self.assignment) == len(self.parser.words_info):
            return True

        # Select next variable
        wid = self._select_unassigned_variable()
        if wid is None:
            return True

        # Try values in order
        for word in self._order_domain_values(wid):
            if not self._is_consistent(wid, word):
                continue

            # Assign
            self.assignment[wid] = word

            # Forward check
            pruned = self._forward_check(wid, word)
            
            if pruned is not None:
                if self.verbose and len(self.assignment) <= 5:
                    info = self.parser.words_info[wid]
                    print(f"  Assigned {wid} (len={info['length']}): {word}")

                if self._backtrack():
                    return True

                # Restore pruned values
                for restore_wid, restore_words in pruned.items():
                    self.domains[restore_wid] |= restore_words

            # Unassign
            del self.assignment[wid]
            self.backtracks += 1

        return False


def update_xml(parser: PuzzleParser, solution: Dict[str, Tuple[str, str]], output_file: str) -> None:
    """Update XML with solution and write to file."""
    # Build coordinate to character map
    coord_to_char: Dict[Tuple[int, int], str] = {}
    for wid, (word, _) in solution.items():
        coords = parser.words_info[wid]['coords']
        for i, coord in enumerate(coords):
            coord_to_char[coord] = word[i]

    # Update word elements
    for elem in parser.crossword.iter():
        if elem.tag.endswith('word'):
            wid = elem.get('id')
            if wid in solution:
                elem.set('solution', solution[wid][0])

    # Update cell elements
    grid = parser.grid
    if grid is not None:
        for cell in grid.iter():
            if cell.tag.endswith('cell'):
                x = cell.get('x')
                y = cell.get('y')
                if x is None or y is None:
                    continue
                    
                try:
                    coord = (int(x), int(y))
                except ValueError:
                    continue

                if coord in coord_to_char:
                    cell.set('solution', coord_to_char[coord])

                # Update clues within cell
                for clue_elem in cell.iter():
                    if clue_elem.tag.endswith('clue'):
                        clue_wid = clue_elem.get('word')
                        if clue_wid in solution:
                            clue_elem.text = solution[clue_wid][1]

    # Strip namespaces for cleaner output
    _strip_namespaces(parser.root)

    # Write output
    parser.tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    print(f"Output written to {output_file}")


def _strip_namespaces(elem: ET.Element) -> None:
    """Remove namespace prefixes from element tags."""
    if elem.tag.startswith('{'):
        elem.tag = elem.tag.split('}', 1)[1]
    for child in elem:
        _strip_namespaces(child)


def main():
    parser = argparse.ArgumentParser(
        description='Generate crossword puzzle from template XML using optimized CSP solver.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_crossword_optimized.py --input template.xml --clues clues.csv --output puzzle.xml
  python generate_crossword_optimized.py -i template.xml -c clues.csv -o puzzle.xml -v
        """
    )
    parser.add_argument('-i', '--input', required=True, help='Input template XML file')
    parser.add_argument('-c', '--clues', required=True, help='Clues CSV file (answer,clue format)')
    parser.add_argument('-o', '--output', required=True, help='Output XML file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    print(f"Loading clues from {args.clues}...")
    generator = CrosswordGenerator(args.clues, verbose=args.verbose)

    print(f"Parsing template from {args.input}...")
    puzzle_parser = PuzzleParser(args.input)
    print(f"Grid size: {puzzle_parser.width}x{puzzle_parser.height}")
    print(f"Word slots: {len(puzzle_parser.words_info)}")

    print("Solving crossword...")
    solver = CSPSolver(generator, puzzle_parser, verbose=args.verbose)
    solution = solver.solve()

    if solution:
        print(f"\nSolution found!")
        print(f"  Words placed: {len(solution)}")
        
        if args.verbose:
            print("\nSolution words:")
            for wid in sorted(solution.keys(), key=lambda x: int(x)):
                word, clue = solution[wid]
                print(f"  {wid}: {word} - {clue[:50]}{'...' if len(clue) > 50 else ''}")

        update_xml(puzzle_parser, solution, args.output)
    else:
        print("Failed to find a solution.")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""A curated library of the core coding-interview patterns — the "learn" reference.
Each entry: when to reach for it, the key idea, and example problems.
"""
from __future__ import annotations

PATTERNS = [
    {"name": "Two Pointers", "when": "Sorted array/string, pairs, or in-place partitioning.",
     "idea": "Move two indices toward each other (or same direction) to shrink the search space in O(n).",
     "examples": ["Valid Palindrome", "3Sum", "Container With Most Water"]},
    {"name": "Sliding Window", "when": "Contiguous subarray/substring with a constraint (max/min/at most k).",
     "idea": "Grow the window on the right; shrink from the left while the constraint breaks.",
     "examples": ["Longest Substring Without Repeating", "Minimum Window Substring", "Max Profit"]},
    {"name": "Fast & Slow Pointers", "when": "Cycle detection, middle of a list, or linked-list problems.",
     "idea": "Two pointers at different speeds; they meet iff there's a cycle.",
     "examples": ["Linked List Cycle", "Find the Duplicate Number", "Reorder List"]},
    {"name": "Binary Search", "when": "Sorted data, or 'minimize/maximize x such that f(x) holds'.",
     "idea": "Halve the search space each step; binary-search on the answer for optimization variants.",
     "examples": ["Search in Rotated Array", "Koko Eating Bananas", "Median of Two Sorted Arrays"]},
    {"name": "Hashing", "when": "Membership, counting, grouping, or O(1) lookups.",
     "idea": "Trade space for time with a dict/set; key by value, prefix, or signature.",
     "examples": ["Two Sum", "Group Anagrams", "Longest Consecutive Sequence"]},
    {"name": "Stack / Monotonic Stack", "when": "Matching, next-greater/smaller, or parsing.",
     "idea": "Keep a stack (often monotonic) to resolve elements as soon as their answer is known.",
     "examples": ["Valid Parentheses", "Daily Temperatures", "Largest Rectangle in Histogram"]},
    {"name": "Heap / Top-K", "when": "K largest/smallest, streaming medians, or scheduling.",
     "idea": "A size-k heap keeps the best k in O(n log k); two heaps track a running median.",
     "examples": ["Kth Largest Element", "K Closest Points", "Find Median from Data Stream"]},
    {"name": "Backtracking", "when": "Generate all combinations/permutations/subsets, or constraint search.",
     "idea": "Choose → explore → un-choose; prune branches that can't lead to a solution.",
     "examples": ["Subsets", "Combination Sum", "N-Queens"]},
    {"name": "BFS", "when": "Shortest path in unweighted graphs / level-order.",
     "idea": "Expand frontier level by level with a queue; first time you reach a node is the shortest.",
     "examples": ["Number of Islands", "Rotting Oranges", "Word Ladder"]},
    {"name": "DFS", "when": "Connectivity, paths, trees, or exhaustive exploration.",
     "idea": "Recurse/stack deep first; great for components, cycles, and tree traversals.",
     "examples": ["Clone Graph", "Course Schedule", "Pacific Atlantic Water Flow"]},
    {"name": "Dynamic Programming", "when": "Overlapping subproblems + optimal substructure.",
     "idea": "Define a state, a recurrence, and base cases; memoize or build a table bottom-up.",
     "examples": ["Coin Change", "Longest Increasing Subsequence", "Edit Distance"]},
    {"name": "Greedy", "when": "Local optimal choice provably leads to global optimum.",
     "idea": "Sort/scan and commit to the best immediate move; prove with an exchange argument.",
     "examples": ["Jump Game", "Merge Intervals", "Gas Station"]},
    {"name": "Intervals", "when": "Overlaps, merging, or scheduling ranges.",
     "idea": "Sort by start (or end); compare each interval to the last kept one.",
     "examples": ["Merge Intervals", "Insert Interval", "Non-overlapping Intervals"]},
    {"name": "Union-Find", "when": "Dynamic connectivity / grouping with merges.",
     "idea": "Disjoint-set with path compression + union by rank → near-O(1) merges/finds.",
     "examples": ["Number of Connected Components", "Redundant Connection", "Graph Valid Tree"]},
]


# Map each library pattern to the LeetCode topic tag(s) that identify it, so a
# "practice this pattern" drilldown can pull matching in-app problems.
PATTERN_TOPICS = {
    "Two Pointers": ["Two Pointers"],
    "Sliding Window": ["Sliding Window"],
    "Fast & Slow Pointers": ["Linked List"],
    "Binary Search": ["Binary Search"],
    "Hashing": ["Hash Table"],
    "Stack / Monotonic Stack": ["Stack", "Monotonic Stack"],
    "Heap / Top-K": ["Heap (Priority Queue)"],
    "Backtracking": ["Backtracking"],
    "BFS": ["Breadth-First Search"],
    "DFS": ["Depth-First Search"],
    "Dynamic Programming": ["Dynamic Programming"],
    "Greedy": ["Greedy"],
    "Intervals": ["Sorting"],  # LeetCode has no "Intervals" tag; sorting is the closest signal
    "Union-Find": ["Union-Find"],
}


def topics_for_pattern(name: str) -> list:
    return PATTERN_TOPICS.get(name, [])


def listing():
    return PATTERNS

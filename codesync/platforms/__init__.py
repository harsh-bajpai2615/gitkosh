"""Platform extractors."""
from __future__ import annotations

from typing import Dict, Type

from .base import Platform
from .leetcode import LeetCode
from .codeforces import Codeforces
from .codechef import CodeChef
from .neetcode import NeetCode
from .atcoder import AtCoder
from .geeksforgeeks import GeeksforGeeks

REGISTRY: Dict[str, Type[Platform]] = {
    LeetCode.name: LeetCode,
    Codeforces.name: Codeforces,
    CodeChef.name: CodeChef,
    NeetCode.name: NeetCode,
    AtCoder.name: AtCoder,
    GeeksforGeeks.name: GeeksforGeeks,
}

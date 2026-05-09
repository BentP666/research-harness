"""paperindex — thin compatibility shim.

The real implementation lives at research_harness.paperindex. This shim
exists so that:

1. `pip install paperindex` continues to work for standalone CLI users
2. Legacy `from paperindex import ...` imports keep working
3. The console_script `paperindex` (declared in pyproject.toml) can
   continue to dispatch via research_harness.paperindex.cli

Do NOT add real logic here. Edit research_harness.paperindex instead.
"""

from research_harness.paperindex import *  # noqa: F401,F403
from research_harness.paperindex import (  # noqa: F401
    EXTRACTABLE_SECTIONS,
    CatalogEntry,
    PaperIndexer,
    PaperRecord,
    SearchResult,
    SectionNode,
    SectionResult,
    StructureMatch,
    StructureResult,
    __version__,
)

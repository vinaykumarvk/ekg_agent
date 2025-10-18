from typing import Tuple, Optional
from ekg_core import export_markdown

def to_markdown_with_citations(final_result: dict, question: str, export: bool = True) -> Tuple[str, Optional[str]]:
    if callable(export_markdown):
        return export_markdown(final=final_result, question=question)
    return final_result.get("answer", ""), None

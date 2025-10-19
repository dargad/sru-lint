"""
Utility for converting unidiff patches to ProcessedFile objects.
"""
from dataclasses import dataclass
from typing import List, Optional
import unidiff

from sru_lint.common.feedback import SourceSpan, create_source_span_from_patch
from sru_lint.common.logging import get_logger

@dataclass
class ProcessedFile:
    """Represents a processed file with source spans for plugin consumption."""
    path: str
    source_span: SourceSpan
    original_patch: Optional[object] = None  # Keep reference to original if needed

def process_patchset(patchset: unidiff.PatchSet) -> List[ProcessedFile]:
    """
    Convert a unidiff PatchSet to a list of ProcessedFile objects.
    
    Args:
        patchset: PatchSet object from unidiff containing all patches
        
    Returns:
        List of ProcessedFile objects with extracted content and metadata
    """
    logger = get_logger("patch_processor")
    logger.debug(f"Processing patchset with {len(patchset)} files")
    
    processed_files = []
    
    for patched_file in patchset:
        logger.debug(f"Processing file: {patched_file.path}")
        
        # Create source span from the patch
        source_span = create_source_span_from_patch(patched_file, include_context=True)
        
        # Create ProcessedFile object
        processed_file = ProcessedFile(
            path=patched_file.path,
            source_span=source_span,
            original_patch=patched_file  # Keep reference if needed
        )
        
        processed_files.append(processed_file)
        
        # Log some statistics
        added_lines = len(source_span.lines_added)
        context_lines = len(source_span.lines_with_context)
        logger.debug(f"File {patched_file.path}: {added_lines} added lines, {context_lines} context lines")
    
    logger.info(f"Processed {len(processed_files)} files from patchset")
    return processed_files


def process_patch_content(patch_content: str) -> List[ProcessedFile]:
    """
    Convert patch content string to a list of ProcessedFile objects.
    
    Args:
        patch_content: Raw patch content as string
        
    Returns:
        List of ProcessedFile objects with extracted content and metadata
    """
    logger = get_logger("patch_processor")
    logger.debug("Parsing patch content")
    
    try:
        patchset = unidiff.PatchSet(patch_content)
        logger.info(f"Successfully parsed patch with {len(patchset)} files")
        return process_patchset(patchset)
    except Exception as e:
        logger.error(f"Failed to parse patch content: {e}")
        return []
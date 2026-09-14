"""
Text chunking utilities for Knowledge Base ingestion.
Provides sentence-aware sliding window chunking with configurable overlap.
"""
import re
from typing import List, Dict, Any


def split_into_sentences(text: str) -> List[str]:
    """Splits text into individual sentences using regex punctuation boundaries."""
    if not text:
        return []
    # Match punctuation followed by space or newline
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    sentences = sentence_endings.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    document_id: str,
    max_words: int = 150,
    overlap_words: int = 30
) -> List[Dict[str, Any]]:
    """
    Chunks a text document using a sentence-aware sliding window.
    
    Args:
        text: The source text to chunk.
        document_id: Unique identifier for the parent document.
        max_words: Target maximum words per chunk.
        overlap_words: Number of words to overlap between consecutive chunks.
        
    Returns:
        List of dictionaries containing chunk_id, chunk_index, and chunk_text.
    """
    if not text or not text.strip():
        return []

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences: List[str] = []
    current_word_count = 0
    chunk_index = 0

    for sentence in sentences:
        word_count = len(sentence.split())
        if current_word_count + word_count > max_words and current_sentences:
            # Emit current chunk
            chunk_content = " ".join(current_sentences)
            chunks.append({
                "chunk_id": f"{document_id}_chunk_{chunk_index}",
                "chunk_index": chunk_index,
                "chunk_text": chunk_content
            })
            chunk_index += 1

            # Keep overlapping sentences from the end
            overlap_sentences = []
            accumulated_overlap = 0
            for s in reversed(current_sentences):
                s_words = len(s.split())
                if accumulated_overlap + s_words <= overlap_words or not overlap_sentences:
                    overlap_sentences.insert(0, s)
                    accumulated_overlap += s_words
                else:
                    break

            current_sentences = overlap_sentences
            current_word_count = sum(len(s.split()) for s in current_sentences)

        current_sentences.append(sentence)
        current_word_count += word_count

    # Add final remaining chunk
    if current_sentences:
        chunk_content = " ".join(current_sentences)
        chunks.append({
            "chunk_id": f"{document_id}_chunk_{chunk_index}",
            "chunk_index": chunk_index,
            "chunk_text": chunk_content
        })

    return chunks

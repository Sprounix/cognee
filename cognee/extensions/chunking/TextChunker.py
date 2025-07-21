from uuid import NAMESPACE_OID, uuid5

from cognee.modules.chunking.Chunker import Chunker
from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.shared.logging_utils import get_logger

logger = get_logger()


class TextChunker(Chunker):
    def read(self):
        for content_text in self.get_text():
            yield DocumentChunk(
                id=uuid5(
                    NAMESPACE_OID, f"{str(self.document.id)}-{self.chunk_index}"
                ),
                text=content_text,
                chunk_size=len(content_text),
                is_part_of=self.document,
                chunk_index=self.chunk_index,
                cut_type="document",
                contains=[],
                metadata={
                    "index_fields": ["text"],
                },
            )

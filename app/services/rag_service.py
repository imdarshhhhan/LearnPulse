import chromadb


class RAGService:
    def __init__(self, collection_name="quiz_bank"):
        self.chroma_client = chromadb.PersistentClient(path="./chroma_storage")
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def add_document_content(
        self,
        text: str,
        pages: list[dict] | None = None,
        material_id: int | None = None,
    ) -> int:
        chunks = []
        metadatas = []
        chunk_size = 500
        overlap = 50
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_str = text[start:end].strip()
            chunks.append(chunk_str)

            # Determine page number from pages offset mapping if available
            page_num = 1
            if pages:
                for p in pages:
                    if p.get("charStart", 0) <= start <= p.get("charEnd", 0):
                        page_num = p.get("pageNumber", 1)
                        break

            metadatas.append({
                "page": page_num,
                "materialId": material_id or 0,
                "chunkIndex": len(chunks) - 1,
            })
            start += (chunk_size - overlap)

        if not chunks:
            return 0

        doc_ids = [
            f"mat_{material_id or 0}_chunk_{i}_{hash(chunks[i]) % 1000000}"
            for i in range(len(chunks))
        ]
        self.collection.add(
            documents=chunks,
            ids=doc_ids,
            metadatas=metadatas,
        )
        return len(chunks)

    def retrieve_grounded_context_with_meta(self, topic: str) -> tuple[str | None, bool, dict]:
        results = self.collection.query(
            query_texts=[topic],
            n_results=1,
            include=["documents", "distances", "metadatas"],
        )

        documents = results.get("documents", [[]])
        distances = results.get("distances", [[]])
        metas = results.get("metadatas", [[]])

        if not documents or not documents[0]:
            return None, False, {}

        context = documents[0][0]
        distance = distances[0][0] if distances and distances[0] else 0.0
        meta = metas[0][0] if metas and metas[0] else {}

        if distance > 1.25:
            return context, False, meta

        return context, True, meta

    def retrieve_grounded_context(self, topic: str) -> tuple[str | None, bool]:
        context, is_grounded, _ = self.retrieve_grounded_context_with_meta(topic)
        return context, is_grounded

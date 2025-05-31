import os

from dotenv import load_dotenv
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


def build_doc_index() -> VectorStoreIndex:
    """Load repository docs and examples into LlamaIndex."""
    # Define the storage directory for the index

    doc_dir = "./storage-docs"
    # Check if the index already exists
    if os.path.exists(doc_dir):
        # Load from disk
        storage_context_doc = StorageContext.from_defaults(persist_dir=doc_dir)
        return load_index_from_storage(storage_context_doc)

    # Build the index if not cached
    usual_docs = SimpleDirectoryReader(
        "./_cmtj/docs", recursive=True, required_exts=[".md", ".txt", ".ipynb"]
    ).load_data()
    knowledge_base_docs = SimpleDirectoryReader("./knowledge_base", recursive=True, required_exts=[".pdf"]).load_data()
    usual_docs.extend(knowledge_base_docs)
    doc_index = VectorStoreIndex.from_documents(usual_docs, show_progress=True)
    doc_index.storage_context.persist(persist_dir=doc_dir)
    return doc_index


print("Building doc index...")
DOC_INDEX = build_doc_index()
SEARCH_ENGINE = DOC_INDEX.as_query_engine(
    similarity_top_k=5,
    include_metadata=True,
    node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.5)],
)
print("Doc index built")


if __name__ == "__main__":
    print(SEARCH_ENGINE.query("What is PIMM simulation?"))

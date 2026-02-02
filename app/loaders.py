import re
from pathlib import Path
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def load_pdfs_with_metadata(pdf_folder: str) -> List[Document]:
    documents = []

    for pdf_path in Path(pdf_folder).glob("*.pdf"):
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()

        for page in pages:
            page.page_content = clean_text(page.page_content)
            page.metadata["source"] = pdf_path.name
            documents.append(page)

    return documents

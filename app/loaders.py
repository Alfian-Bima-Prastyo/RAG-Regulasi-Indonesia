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
            text = clean_text(page.page_content)
            page_number = page.metadata.get("page", None)

            if not text:
                continue

            if page_number == 0:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": pdf_path.name,
                            "page": page_number,
                            "is_identity_page": True
                        }
                    )
                )
            else:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": pdf_path.name,
                            "page": page_number,
                            "is_identity_page": False
                        }
                    )
                )

    return documents

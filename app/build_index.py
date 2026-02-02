from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from loaders import load_pdfs_with_metadata
from config import PDF_DIR, CHROMA_DIR

def build_index():
    docs = load_pdfs_with_metadata(PDF_DIR)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300
    )
    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(
        model_name="LazarusNLP/all-indo-e5-small-v4",
        model_kwargs = {'device':'cpu'}
    )

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    vectorstore.persist()
    print(" Chroma index built ")

if __name__ == "__main__":
    build_index()

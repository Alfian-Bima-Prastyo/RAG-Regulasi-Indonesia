# RAG Regulasi Indonesia

Project ini merupakan implementasi sederhana **Retrieval-Augmented Generation (RAG)** untuk sistem tanya jawab berbasis dokumen regulasi di Indonesia, seperti **Undang-Undang (UU)**, **POJK**, dan **SEOJK**.

Project ini dikembangkan secara mandiri sebagai bagian dari portofolio, dengan jumlah dokumen yang masih terbatas dan fokus pada eksplorasi alur RAG end-to-end.

---

## Gambaran Umum

Alur sistem secara garis besar:

1. Dokumen regulasi (PDF) dimuat dan dipotong menjadi beberapa chunk
2. Setiap chunk diubah menjadi embedding
3. Embedding disimpan di vector database (Chroma)
4. Pertanyaan pengguna diproses dengan:
   - Retrieval dokumen relevan
   - Reranking
   - Prompting ke LLM
5. Sistem mengembalikan jawaban beserta sumber dokumen

---

## Teknologi yang Digunakan

- **Python**
- **FastAPI** – API server
- **LangChain** – RAG pipeline
- **ChromaDB** – Vector database
- **Deepseek-r1**
- **Indo E5 Embeddings**
- **PDF Loader**

---



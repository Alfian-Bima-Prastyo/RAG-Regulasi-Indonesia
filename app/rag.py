from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
import re

from app.loaders import load_pdfs_with_metadata
from app.retriever import HybridRetriever
from app.reranker import AdvancedReranker
from app.prompt import ADVANCED_PROMPT_TEMPLATE
from app.config import CHROMA_DIR, PDF_DIR, TOP_K

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="LazarusNLP/all-indo-e5-small-v4",
    model_kwargs={'device':'cpu'}
)

# Initialize vectorstore
vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings
)

# Load documents
docs = load_pdfs_with_metadata(PDF_DIR)

# Initialize components
reranker = AdvancedReranker()
retriever = HybridRetriever(vectorstore, docs, k=TOP_K)

# Initialize LLM
llm = Ollama(model="deepseek-r1:latest", temperature=0)

def calculate_confidence(selected_docs, query):
    """Calculate confidence score for the answer"""
    scores = {
        "retrieval_quality": 0.0,
        "document_consistency": 0.0,
        "query_coverage": 0.0
    }
    
    if not selected_docs or len(selected_docs) == 0:
        return {
            "overall": 0.0, 
            "details": scores, 
            "level": "VERY_LOW",
            "explanation": "Tidak ada dokumen relevan ditemukan"
        }
    
    avg_score = sum(score for _, score in selected_docs) / len(selected_docs)
    scores["retrieval_quality"] = min(avg_score / 200, 1.0)
    
    sources = [doc.metadata.get('source', 'unknown') for doc, _ in selected_docs]
    unique_sources = len(set(sources))
    scores["document_consistency"] = 1.0 - (unique_sources / max(len(sources), 1))
    
    query_terms = set(query.lower().split())
    covered_terms = set()
    
    for doc, _ in selected_docs[:3]:
        content_terms = set(doc.page_content.lower().split())
        covered_terms.update(query_terms.intersection(content_terms))
    
    if len(query_terms) > 0:
        scores["query_coverage"] = len(covered_terms) / len(query_terms)
    
    overall = (
        scores["retrieval_quality"] * 0.4 +
        scores["document_consistency"] * 0.3 +
        scores["query_coverage"] * 0.3
    )
    
    if overall >= 0.8:
        level = "VERY_HIGH"
        explanation = "Sistem sangat yakin dengan jawaban ini berdasarkan dokumen yang sangat relevan"
    elif overall >= 0.6:
        level = "HIGH"
        explanation = "Sistem cukup yakin dengan jawaban ini, dokumen pendukung cukup baik"
    elif overall >= 0.4:
        level = "MEDIUM"
        explanation = "Sistem moderat yakin, disarankan untuk verifikasi dengan dokumen asli"
    elif overall >= 0.2:
        level = "LOW"
        explanation = "Sistem kurang yakin, informasi terbatas. Wajib verifikasi manual"
    else:
        level = "VERY_LOW"
        explanation = "Sistem sangat tidak yakin, sangat disarankan mencari sumber lain"
    
    return {
        "overall": overall,
        "percentage": f"{overall*100:.1f}%",
        "details": scores,
        "level": level,
        "explanation": explanation
    }

def extract_snippet(doc, query):
    query_terms = query.lower().split()
    sentences = doc.page_content.split('. ')
    
    if sentences:
        best_sentence = max(
            sentences,
            key=lambda s: sum(1 for term in query_terms if term in s.lower())
        )
        snippet = best_sentence[:200] + "..." if len(best_sentence) > 200 else best_sentence
    else:
        snippet = doc.page_content[:200] + "..."
    
    return snippet

def ask(question):
    retrieved = retriever.retrieve(question)
    
    reranked = reranker.rerank(retrieved, query=question)
    
    selected_docs = reranked[:TOP_K]

    query_pattern = r'(POJK|SEOJK|UU)\s*(\d+)[/\s]*(20\d{2})'
    query_match = re.search(query_pattern, question.upper())
    
    warning = ""
    if query_match:
        query_reg = query_match.group(0).replace(' ', '_').replace('/', '_')
        doc_found = any(
            query_reg in doc.metadata.get('source', '').upper() 
            for doc, _ in selected_docs[:3]
        )
        
        if not doc_found:
            warning = f"⚠️ Dokumen {query_match.group(0)} tidak ditemukan dalam sistem.\n\n"

    if 'seojk' in question.lower():
        has_seojk = any('SEOJK' in doc.metadata.get('source', '').upper() 
                    for doc, _ in selected_docs[:3])
        if not has_seojk:
            warning = "⚠️ SEOJK spesifik tidak ditemukan. Menggunakan POJK terkait.\n\n"
    elif 'pojk' in question.lower():
        has_pojk = any('POJK' in doc.metadata.get('source', '').upper() 
                    for doc, _ in selected_docs[:3])
        if not has_pojk:
            warning = "⚠️ POJK spesifik tidak ditemukan. Menggunakan regulasi terkait.\n\n"
    elif 'uu' in question.lower() or 'undang-undang' in question.lower():
        has_uu = any('UU' in doc.metadata.get('source', '').upper() 
                    for doc, _ in selected_docs[:3])
        if not has_uu:
            warning = "⚠️ UU spesifik tidak ditemukan. Menggunakan regulasi terkait.\n\n"
    
    confidence_info = calculate_confidence(selected_docs, question)
    
    context_chunks = []
    sources = []
    
    for doc, score in selected_docs:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "N/A")
        
        context_chunks.append(
            f"[Sumber: {source}, Halaman: {page}, Score: {score:.1f}]\n{doc.page_content}"
        )
        
        snippet = extract_snippet(doc, question)
        
        sources.append({
            "document": source,
            "page": page,
            "score": score,
            "snippet": snippet
        })
    
    context = "\n\n".join(context_chunks)
    
    prompt = ADVANCED_PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )
    
    answer = llm.invoke(prompt)
    
    return {
        "answer": warning + answer,
        "sources": sources,
        "confidence": confidence_info,
        "num_sources": len(selected_docs)
    }

def get_stats():
    return reranker.get_report()

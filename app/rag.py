from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
import re

from app.loaders import load_pdfs_with_metadata
from app.retriever import HybridRetriever
from app.reranker import AdvancedReranker
from app.strict_context import StrictRegulationContextBuilder
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
context_builder = StrictRegulationContextBuilder()
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


def ask(question: str):
    print("\n=== DEBUG ASK ===")
    print("Query:", question)

    # 1. REGULATION PARSER
    REGEX = r'(pojk|seojk|uu)\s*(?:no\.|nomor)?\s*(\d+)\s*(?:tahun|/)?\s*(\d{4})'
    query_match = re.search(REGEX, question, re.IGNORECASE)

    if not query_match:
        return {
            "answer": "Pertanyaan tidak menyebut regulasi secara eksplisit.",
            "sources": [],
            "confidence": {"overall": 0.0},
            "num_sources": 0,
            "validation_status": {
                "valid": False,
                "error": "No explicit regulation reference"
            }
        }

    reg_type, reg_num, reg_year = query_match.groups()
    reg_type = reg_type.upper()
    reg_num = str(int(reg_num))  
    expected_filename = f"{reg_type}_{reg_num}_{reg_year}"

    print("\n=== DEBUG REGULATION PARSED ===")
    print("Type :", reg_type)
    print("Num  :", reg_num)
    print("Year :", reg_year)
    print("Expect:", expected_filename)

    # 2. RETRIEVAL
    retrieved = retriever.retrieve(question)

    print("\n=== DEBUG RETRIEVER RAW ===")
    for i, doc in enumerate(retrieved[:10], 1):
        print(f"{i}. {doc.metadata.get('source')} | page={doc.metadata.get('page')}")

    # 3. RERANK
    reranked = reranker.rerank(retrieved, query=question)

    print("\n=== DEBUG RERANKED ===")
    for i, (doc, score) in enumerate(reranked[:10], 1):
        print(f"{i}. {doc.metadata.get('source')} | score={score:.2f}")

    # 4. STRICT REGULATION LOCK
    locked_docs = [
        (doc, score)
        for doc, score in reranked
        if expected_filename in doc.metadata.get("source", "").upper()
    ]

    if not locked_docs:
        return {
            "answer": f" Dokumen {reg_type} {reg_num} Tahun {reg_year} tidak tersedia di sistem.",
            "sources": [],
            "confidence": {"overall": 0.0},
            "num_sources": 0,
            "validation_status": {
                "valid": False,
                "error": "Regulation not found"
            }
        }

    print("\n=== DEBUG LOCKED DOCS ===")
    for i, (doc, score) in enumerate(locked_docs[:5], 1):
        print(f"{i}. {doc.metadata.get('source')} | page={doc.metadata.get('page')} | score={score:.1f}")

    # 5. AUTO SPLIT(Definition)
    q = question.lower()
    is_definition = any(k in q for k in [
        "apa yang dimaksud",
        "apa itu",
        "pengertian"
    ])

    if is_definition:
        selected_docs = [
            (doc, score)
            for doc, score in locked_docs
            if doc.metadata.get("page") in [0, 1]
        ][:2]
    else:
        selected_docs = locked_docs[:5]

    print("\n=== DEBUG AUTO SPLIT ===")
    print("Definition mode:", is_definition)
    for i, (doc, score) in enumerate(selected_docs, 1):
        print(f"{i}. {doc.metadata.get('source')} | page={doc.metadata.get('page')}")

    # 6. CONTEXT BUILDER (STRICT)
    context = "## DOKUMEN YANG TERSEDIA DI SISTEM (STRICT REGULATION MODE)\n\n"
    context += " HANYA dokumen berikut yang BOLEH digunakan.\n\n"

    sources = []

    for i, (doc, score) in enumerate(selected_docs, 1):
        context += f"### DOKUMEN #{i}: {doc.metadata.get('source')}\n"
        context += f" Halaman: {doc.metadata.get('page')}\n"
        context += f" Relevance Score: {score:.1f}\n\n"
        context += f"{doc.page_content}\n\n"
        context += "=" * 80 + "\n\n"

        sources.append({
            "document": doc.metadata.get("source"),
            "page": doc.metadata.get("page"),
            "score": score
        })

    print("\n=== DEBUG FULL CONTEXT SENT TO LLM ===")
    print(context[:3000])

    # 7. PROMPT & LLM
    prompt = ADVANCED_PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )

    answer = llm.invoke(prompt)
    answer_text = str(answer)

    # 8. POST VALIDATION
    validation = validate_citations(answer_text, selected_docs)

    if not validation["valid"]:
        answer_text = f" PERINGATAN SISTEM: {validation['error']}\n\n" + answer_text

    confidence_info = calculate_confidence(selected_docs, question)

    return {
        "answer": answer_text,
        "sources": sources,
        "confidence": confidence_info,
        "num_sources": len(selected_docs),
        "validation_status": validation
    }


def get_stats():
    return reranker.get_report()

def validate_citations(answer, source_docs):
    available_docs = [doc.metadata.get('source', '').upper() for doc, _ in source_docs]
    
    pattern = r'(UU|POJK|SEOJK)[\s_]*(?:No\.|Nomor)?\s*(\d+)[\s_/]*(?:Tahun\s*)?(\d{4})'

    mentioned = re.findall(pattern, answer, re.IGNORECASE)
    
    hallucinations = []
    
    for reg_type, num, year in mentioned:
        expected_file = f"{reg_type.upper()}_{num}_{year}.PDF"
        
        found = any(expected_file in doc for doc in available_docs)
        
        if not found:
            hallucinations.append(f"{reg_type} {num}/{year}")
    
    if hallucinations:
        return {
            'valid': False,
            'error': f"Jawaban menyebut dokumen yang tidak tersedia: {', '.join(hallucinations)}"
        }
    
    return {'valid': True, 'error': None}

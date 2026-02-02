import gradio as gr
import warnings
warnings.filterwarnings('ignore')

from app import ask, get_stats

# Example questions
examples = [
    ["Apa yang dimaksud dengan POJK 27 Tahun 2022?"],
    ["Bank mana yang wajib membentuk Capital Conservation Buffer?"],
    ["Kapan seluruh bank wajib memperhitungkan aset tertimbang menurut risiko untuk Risiko Pasar?"],
    ["Apa itu Otoritas Jasa Keuangan menurut UU 21 2008?"],
    ["Apa saja prinsip pengelolaan teknologi informasi bank menurut POJK 11 2022?"],
]

def format_citations(sources):
    """Format source citations with snippets"""
    if not sources:
        return "Tidak ada sumber rujukan"
    
    formatted = []
    seen = set()
    
    for i, source in enumerate(sources, 1):
        doc = source.get("document", "Unknown")
        page = source.get("page", "N/A")
        score = source.get("score", 0)
        snippet = source.get("snippet", "")
        
        key = f"{doc}_{page}"
        
        if key not in seen:
            citation_text = f"[{i}] {doc} (Halaman {page}, Skor: {score:.1f})"
            
            if snippet:
                citation_text += f"\n> {snippet}"
            
            formatted.append(citation_text)
            seen.add(key)
    
    return "\n\n".join(formatted)

def format_confidence(confidence_info):
    level = confidence_info.get("level", "UNKNOWN")
    percentage = confidence_info.get("percentage", "0%")
    explanation = confidence_info.get("explanation", "")
    
    if level in ["VERY_HIGH", "HIGH"]:
        color = "green"
    elif level == "MEDIUM":
        color = "orange"
    else:
        color = "red"
    
    confidence_text = f"""
**Confidence Level:** <span style="color: {color}; font-weight: bold;">{level}</span> ({percentage})

{explanation}
"""
    
    return confidence_text

def show_fairness_stats():
    """Display fairness statistics"""
    report = get_stats()
    
    if report["total_retrievals"] == 0:
        return "Belum ada data retrieval"
    
    stats_text = f"""
## Fairness Statistics

**Total Documents Retrieved:** {report['total_retrievals']}
**Total Documents Selected:** {report['total_selected']}

### Breakdown by Document Type:
"""
    
    for reg_type, stats in report['by_type'].items():
        stats_text += f"\n- **{reg_type}:** Retrieved {stats['retrieved']}, Selected {stats['selected']} (Selection Rate: {stats['selection_rate']})"
    
    if report['by_type']:
        selection_rates = [
            float(stats['selection_rate'].replace('%', '')) 
            for stats in report['by_type'].values()
        ]
        
        if len(selection_rates) >= 2:
            max_rate = max(selection_rates)
            min_rate = min(selection_rates)
            
            if max_rate - min_rate > 30:
                stats_text += "\n\n**Warning:** Terdeteksi kemungkinan bias dalam selection rate (perbedaan > 30%)"
            else:
                stats_text += "\n\n**Good:** Selection rate relatif seimbang antar tipe dokumen"
    
    return stats_text

def ask_question(question):
    if not question.strip():
        return "Silakan masukkan pertanyaan", "", "", ""
    
    try:
        result = ask(question)
        
        # Extract results
        answer = result["answer"]
        sources = result.get("sources", [])
        confidence_info = result.get("confidence", {})
        num_sources = result.get("num_sources", 0)
        
        # Format outputs
        citations = format_citations(sources)
        confidence_display = format_confidence(confidence_info)
        
        stats_text = f"""
**Dokumen Digunakan:** {num_sources}

{confidence_display}
"""
        
        return answer, citations, stats_text
        
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
        return error_msg, "", ""

# Custom CSS
custom_css = """
#title {
    text-align: center;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5em;
    font-weight: bold;
    margin-bottom: 10px;
}
#subtitle {
    text-align: center;
    color: #666;
    font-size: 1.1em;
    margin-bottom: 20px;
}
.citation-box {
    background-color: #f0f7ff;
    border-left: 4px solid #3b82f6;
    padding: 15px;
    border-radius: 5px;
    font-family: monospace;
}
"""

# Create Gradio interface
with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.Markdown("<h1 id='title'>RAG Peraturan Perbankan Indonesia</h1>")
    gr.Markdown("<p id='subtitle'>Sistem Question-Answering berbasis AI untuk Peraturan OJK, POJK, SEOJK, dan UU Perbankan</p>")
    
    with gr.Row():
        with gr.Column(scale=2):
            question_input = gr.Textbox(
                label="Pertanyaan Anda",
                placeholder="Contoh: Apa yang dimaksud dengan POJK 27 Tahun 2022?",
                lines=3
            )
            
            submit_btn = gr.Button("Tanya", variant="primary", size="lg")
            
        with gr.Column(scale=3):
            answer_output = gr.Textbox(
                label="Jawaban",
                lines=12
            )
            
            with gr.Accordion("Confidence & Statistics", open=True):
                stats_output = gr.Markdown(
                    value="Belum ada statistik"
                )
            
            citations_output = gr.Textbox(
                label="Sumber Rujukan",
                lines=8,
                elem_classes="citation-box"
            )
    
    with gr.Accordion("Fairness Monitoring", open=False):
        fairness_stats = gr.Markdown("Belum ada data")
        refresh_fairness_btn = gr.Button("Refresh Fairness Stats")
        
        refresh_fairness_btn.click(
            fn=show_fairness_stats,
            outputs=fairness_stats
        )
    
    # Examples section
    gr.Markdown("### Contoh Pertanyaan:")
    gr.Examples(
        examples=examples,
        inputs=[question_input],
        outputs=[answer_output, citations_output, stats_output],
        fn=ask_question,
        cache_examples=False
    )
    
    # Information section
    gr.Markdown("""
    ---
    ### Informasi:
    - **Model:** DeepSeek-R1 (via Ollama)
    - **Embeddings:** LazarusNLP/all-indo-e5-small-v4
    - **Metode:** Hybrid Retrieval + Advanced Reranking + Confidence Scoring
    - **Dokumen:** POJK, SEOJK, dan UU Perbankan Indonesia
    
    ### Cara Penggunaan:
    1. Masukkan pertanyaan tentang peraturan perbankan Indonesia
    2. Klik "Tanya" dan tunggu beberapa detik
    3. Lihat jawaban lengkap dengan confidence score dan sitasi sumber
    4. Gunakan "Fairness Monitoring" untuk melihat distribusi retrieval
    
    ### Catatan:
    - Sistem menggunakan AI generatif - selalu verifikasi dengan dokumen asli
    - Confidence score menunjukkan tingkat keyakinan sistem terhadap jawaban
    - Untuk keperluan legal formal, konsultasikan dengan ahli hukum
    """)
    
    submit_btn.click(
        fn=ask_question,
        inputs=[question_input],
        outputs=[answer_output, citations_output, stats_output]
    )

if __name__ == "__main__":
    demo.launch()

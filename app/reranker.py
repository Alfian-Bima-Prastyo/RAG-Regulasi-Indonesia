import re

class AdvancedReranker:
    def __init__(self):
        self.base_priority = {
            "UU": 200,
            "POJK": 100,
            "SEOJK": 80
        }

        self.retrieval_stats = {
            "UU": {"count": 0, "selected": 0},
            "POJK": {"count": 0, "selected": 0},
            "SEOJK": {"count": 0, "selected": 0}
        }

    def _adapt_priority_to_query(self, query):
        query_lower = query.lower()
        adapted_priority = self.base_priority.copy()

        if any(w in query_lower for w in ["undang-undang", "uu ", "uu:"]):
            adapted_priority["UU"] = 80
        elif any(w in query_lower for w in ["pojk", "peraturan ojk"]):
            adapted_priority["POJK"] = 80
        elif any(w in query_lower for w in ["seojk", "surat edaran"]):
            adapted_priority["SEOJK"] = 80
        else:
            adapted_priority = {"UU": 50, "POJK": 50, "SEOJK": 50}

        return adapted_priority

    def _extract_year_from_query(self, query):
        m = re.search(r'(tahun\s+)?(20\d{2})', query.lower())
        return int(m.group(2)) if m else None

    def _extract_regulation_from_query(self, query):
        m = re.search(r'(pojk|seojk|uu)\s*(nomor\s*)?\d+', query.lower())
        return m.group(0).upper().replace('NOMOR', '').strip() if m else None

    def score_document(self, doc, query, base_rank):
        explanations = []
        score = 0

        content_lower = doc.page_content.lower()
        query_lower = query.lower()
        metadata = doc.metadata
        source = metadata.get("source", "unknown")

        reg_type = source.split('_')[0] if source != "unknown" and "_" in source else "UNKNOWN"

        if reg_type in self.retrieval_stats:
            self.retrieval_stats[reg_type]["count"] += 1

        rank_score = 100 / (base_rank + 1)
        score += rank_score
        explanations.append(f"Peringkat retrieval #{base_rank+1}: +{rank_score:.1f}")

        qt = set(query_lower.split())
        ct = set(content_lower.split())
        overlap = qt & ct
        overlap_score = len(overlap) * 5
        score += overlap_score
        explanations.append(f"Kata kunci cocok ({len(overlap)}/{len(qt)}): +{overlap_score:.1f}")

        adapted_priority = self._adapt_priority_to_query(query)
        if reg_type in adapted_priority:
            p = adapted_priority[reg_type] 
            score += p
            explanations.append(f"Prioritas tipe {reg_type}: +{p:.1f}")

        query_year = self._extract_year_from_query(query)
        if query_year and source != "unknown":
            sm = re.search(r'(\d{4})', source)
            if sm:
                source_year = int(sm.group(1))
                diff = abs(source_year - query_year)

                if source_year == query_year:
                    score += 100
                    explanations.append(f"Tahun exact match ({query_year}): +100")
                elif diff <= 3:
                    score += 50
                    explanations.append(f"Tahun relevan ({source_year}): +50")
                elif diff <= 5:
                    score += 20
                    explanations.append(f"Tahun cukup relevan ({source_year}): +20")
                else:
                    penalty = diff * 0.5
                    score -= penalty
                    explanations.append(f"Perbedaan tahun ({source_year} vs {query_year}): -{penalty:.1f}")

        query_reg = self._extract_regulation_from_query(query)
        if query_reg and source != "unknown":
            source_reg = re.sub(r'_\d{4}\.pdf', '', source).replace('_', ' ')
            if query_reg.lower() in source_reg.lower():
                score += 500
                explanations.append(f"Nama regulasi match ({query_reg}): +200")
            else:
                score -= 50   # Penalty for wrong document
                explanations.append(f"Document mismatch: -50")

        important_terms = [
            "pasal", "ayat", "huruf", "angka",
            "ketentuan", "peraturan", "undang-undang",
            "bank", "risiko", "modal", "likuiditas"
        ]

        term_count = sum(
            1 for t in important_terms
            if t in query_lower and t in content_lower
        )

        if term_count:
            ts = term_count * 2
            score += ts
            explanations.append(f"Istilah penting ({term_count}): +{ts:.1f}")

        return score, explanations

    def rerank(self, docs, query=None):
        scored = []

        for rank, doc in enumerate(docs):
            if query:
                score, explanations = self.score_document(doc, query, rank)
            else:
                score = self._simple_score(doc)
                explanations = ["Simple scoring (no query)"]

            scored.append({
                "doc": doc,
                "score": score,
                "explanations": explanations
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        for item in scored[:5]:
            source = item["doc"].metadata.get("source", "unknown")
            reg_type = source.split('_')[0] if "_" in source else "UNKNOWN"
            if reg_type in self.retrieval_stats:
                self.retrieval_stats[reg_type]["selected"] += 1

        return [(item["doc"], item["score"]) for item in scored]

    def _simple_score(self, doc):
        text = doc.page_content.lower()
        s = 0
        if "pojk" in text:
            s += 3
        if "pasal" in text:
            s += 2
        if "ayat" in text:
            s += 1
        return s

    def get_report(self):
        report = {
            "total_retrievals": sum(v["count"] for v in self.retrieval_stats.values()),
            "total_selected": sum(v["selected"] for v in self.retrieval_stats.values()),
            "by_type": {}
        }

        for k, v in self.retrieval_stats.items():
            if v["count"] > 0:
                rate = v["selected"] / v["count"]
                report["by_type"][k] = {
                    "retrieved": v["count"],
                    "selected": v["selected"],
                    "selection_rate": f"{rate*100:.1f}%"
                }

        return report

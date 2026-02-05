import re

class StrictRegulationContextBuilder:
    REG_PATTERN = r'(POJK|SEOJK|UU)\s*(?:No\.|Nomor)?\s*(\d+)\s*(?:/|Tahun)?\s*(\d{4})'

    def parse_target_regulation(self, question: str):
        m = re.search(self.REG_PATTERN, question.upper())
        if not m:
            return None

        reg_type, num, year = m.groups()
        num = str(int(num))
        expected_filename = f"{reg_type}_{num}_{year}"
        return {
            "type": reg_type,
            "number": num,
            "year": year,
            "expected_filename": expected_filename
        }

    def filter_documents(self, selected_docs, question: str):
        target = self.parse_target_regulation(question)
        if not target:
            return selected_docs, None

        expected = target["expected_filename"]

        matched = [
            (doc, score)
            for doc, score in selected_docs
            if expected in doc.metadata.get("source", "").upper()
        ]

        if not matched:
            return [], {
                "valid": False,
                "error": f"Dokumen {target['type']} {target['number']}/{target['year']} tidak tersedia"
            }
        matched.sort(key=lambda x: x[0].metadata.get("page", 999))

        return matched, {
            "valid": True,
            "target": target
        }

    def build_context(self, filtered_docs):
        context = "## DOKUMEN YANG TERSEDIA DI SISTEM (STRICT MODE):\n\n"

        for i, (doc, score) in enumerate(filtered_docs, 1):
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "N/A")

            context += f"### DOKUMEN #{i}: {source}\n"
            context += f" **Halaman:** {page}\n"
            context += f" **Relevance Score:** {score:.1f}\n\n"
            context += f"**ISI DOKUMEN:**\n{doc.page_content}\n\n"
            context += "=" * 80 + "\n\n"

        return context

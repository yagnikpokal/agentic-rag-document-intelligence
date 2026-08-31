"""Minimal PDF writer used to seed the local knowledge base."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "pdfs"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        paragraph = raw.rstrip()
        if not paragraph:
            lines.append("")
            continue
        while len(paragraph) > width:
            cut = paragraph.rfind(" ", 0, width)
            if cut < 20:
                cut = width
            lines.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()
        lines.append(paragraph)
    return lines


def write_pdf(path: Path, title: str, body: str) -> None:
    """Write a multi-page Helvetica text PDF that Docling can parse."""
    wrapped = _wrap(f"{title}\n\n{body}")
    lines_per_page = 48
    pages = [wrapped[i : i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)] or [[title]]

    objects: list[bytes] = []

    def add(payload: str) -> int:
        objects.append(payload.encode("latin-1", errors="replace"))
        return len(objects)

    add("<< /Type /Catalog /Pages 2 0 R >>")
    page_count = len(pages)
    page_ids = list(range(3, 3 + page_count))
    content_obj_ids = list(range(3 + page_count, 3 + 2 * page_count))
    font_id = 3 + 2 * page_count
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    add(f"<< /Type /Pages /Count {page_count} /Kids [{kids}] >>")

    content_payloads: list[str] = []
    for page_id, content_id, page_lines in zip(page_ids, content_obj_ids, pages):
        stream_lines = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
        for line in page_lines:
            stream_lines.append(f"({_escape(line)}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_payloads.append(stream)
        add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )

    for stream in content_payloads:
        payload = f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream"
        add(payload)

    add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode())
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")
    xref_pos = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode())
    buffer.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buffer))


DOCUMENTS: dict[str, tuple[str, str]] = {
    "aethercorp_employee_handbook.pdf": (
        "AetherCorp Employee Handbook",
        """
Document ID: HR-HB-2026-01
Effective date: 1 January 2026
Owner: People Operations

1. Purpose
This handbook describes employment policies for all AetherCorp full-time, part-time, and contract staff.

2. Paid time off
Full-time employees receive 20 days of paid time off (PTO) each calendar year. PTO accrues at 1.67 days per month. Unused PTO may be carried over up to 5 days into the next year. Contractors do not receive PTO unless specified in their statement of work.

3. Sick leave
Employees receive 10 sick days per year. Sick leave does not pay out at termination. A doctor's note is required for absences longer than 3 consecutive working days.

4. Remote work
AetherCorp uses a hybrid model. Employees must be in a company office Tuesday through Thursday. Monday and Friday are optional remote days. Exceptions require written approval from a director. Core collaboration hours are 10:00 to 16:00 in the employee's local timezone.

5. Parental leave
Primary caregivers receive 16 weeks of paid parental leave. Secondary caregivers receive 6 weeks. Leave may begin up to 2 weeks before the expected due date or adoption date.

6. Expenses
Travel and software expenses above 250 USD require pre-approval in the Nimbus expense module. Meals during travel are capped at 75 USD per day.

7. Code of conduct
Harassment, discrimination, and retaliation are prohibited. Report incidents to people@aethercorp.example or the anonymous ethics hotline 1-800-555-0199.
""",
    ),
    "aethercorp_product_guide.pdf": (
        "Nimbus Platform Product Guide",
        """
Document ID: PRD-NIMBUS-4.2
Product: Nimbus Document Intelligence
Version: 4.2

1. Overview
Nimbus is AetherCorp's document intelligence platform. It ingests PDFs, contracts, and knowledge-base articles, then answers questions with citations.

2. Editions
Starter: 5 seats, 10,000 pages per month, 7-day retention of traces.
Team: 50 seats, 200,000 pages per month, 90-day retention, SSO.
Enterprise: unlimited seats, private networking, dedicated retrieval cluster, 365-day retention, custom retention legal hold.

3. Key features
- Semantic search across PDF and HTML sources
- Agentic retrieval that rewrites follow-up questions
- Citation-backed answers
- Prompt library with versioned YAML prompts
- Evaluation workspace that reports faithfulness and latency

4. Nimbus Query Language
Users may prefix a question with site:contracts or site:policies to constrain retrieval. The default collection is "global".

5. Limits
Maximum upload size is 50 MB per file. Supported types are PDF, DOCX, and HTML. Images inside PDFs are OCR'd when the OCR add-on is enabled.

6. SLAs
Team edition monthly uptime target is 99.5%. Enterprise uptime target is 99.9%. P1 incidents are acknowledged within 15 minutes for Enterprise customers.

7. Pricing
Starter is 49 USD per user per month. Team is 129 USD per user per month. Enterprise pricing is quoted by sales@aethercorp.example.
""",
    ),
    "aethercorp_engineering_standards.pdf": (
        "AetherCorp Engineering Standards",
        """
Document ID: ENG-STD-2026
Audience: Software engineering, SRE, data

1. Source control
The default branch is main. Feature work happens on branches named feat/<ticket>-<slug>. Pull requests require one approving review and a green CI pipeline. Direct pushes to main are blocked.

2. Python
Services use Python 3.13, uv for lockfiles, and Ruff for linting. Public functions must have type hints. FastAPI is the standard HTTP framework.

3. Observability
Every inference call must emit an OpenTelemetry span. Traces are exported to Arize Phoenix. Service logs use structured JSON. RED metrics (rate, errors, duration) are required for user-facing APIs.

4. Incident response
Sev-1: customer-facing outage or data loss. Page the on-call engineer and open an incident channel named inc-YYYYMMDD-shortname. A written postmortem is due within 3 business days.
Sev-2: degraded performance. Respond within 30 minutes during business hours.

5. Secrets
Secrets live in the platform vault. They must never be committed to git. Rotate leaked credentials within 1 hour.

6. Retrieval systems
Production RAG services store embeddings in PostgreSQL with pgvector. Embedding dimension must match the configured model. Hybrid search (vector + keyword) is required for policy corpora.

7. On-call
Primary on-call rotates weekly. Handoff is Friday 16:00 UTC. The on-call engineer must have laptop access and the production runbook at https://runbooks.aethercorp.example.
""",
    ),
    "aethercorp_security_policy.pdf": (
        "AetherCorp Information Security Policy",
        """
Document ID: SEC-POL-2026-04
Classification: Internal

1. Data classification
Public: marketing pages. Internal: product specs and engineering standards. Confidential: customer documents, embeddings, and traces. Restricted: credentials, payroll, and government identifiers.

2. Access control
Production access uses SSO plus hardware security keys. Privileged roles are reviewed quarterly. Shared root passwords are forbidden.

3. Retention
Customer documents remain until the customer deletes them or the contract ends. Traces for Starter accounts are deleted after 7 days. Team traces after 90 days. Enterprise traces after 365 days unless a legal hold is active.

4. Encryption
Data in transit uses TLS 1.2 or newer. Data at rest in PostgreSQL uses AES-256. Embedding indexes inherit the same volume encryption.

5. Vendor LLM use
Customer content must not be sent to a third-party model provider unless the customer has enabled that provider in the Nimbus admin console. The default deployment uses a self-hosted Ollama model named llama3.2.

6. Breach notification
Security must be notified at security@aethercorp.example within 1 hour of suspected unauthorized access. Customers are notified within 72 hours when Confidential or Restricted data is involved.

7. Acceptable use
Staff may not paste customer documents into personal AI tools. Violations may result in termination.
""",
    ),
}


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (title, body) in DOCUMENTS.items():
        dest = PDF_DIR / filename
        write_pdf(dest, title, body)
        print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

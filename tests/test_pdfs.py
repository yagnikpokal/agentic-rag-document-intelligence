from pathlib import Path

from scripts.generate_sample_pdfs import DOCUMENTS, write_pdf


def test_pdf_writer_creates_parseable_header(tmp_path: Path):
    dest = tmp_path / "sample.pdf"
    write_pdf(dest, "Title", "Hello knowledge base.\nSecond line.")
    data = dest.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert b"%%EOF" in data
    assert dest.stat().st_size > 200


def test_sample_corpus_covers_four_policies():
    assert set(DOCUMENTS) == {
        "aethercorp_employee_handbook.pdf",
        "aethercorp_product_guide.pdf",
        "aethercorp_engineering_standards.pdf",
        "aethercorp_security_policy.pdf",
    }
    handbook = DOCUMENTS["aethercorp_employee_handbook.pdf"][1]
    assert "20 days" in handbook

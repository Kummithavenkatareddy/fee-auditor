import io
import json
from datetime import date
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.schemas.common import FieldStatus
from app.schemas.document import DocumentExtraction, ExtractedField, ExtractedLineItem
from app.services.extractor import (
    is_receipt_filename,
    determine_model,
    _extract_date_value,
)
from app.services.validator import (
    _parse_iso_date,
    validate_v04_outside_academic_term,
    validate_v05_low_confidence,
    apply_all_validation_rules,
)
from app.services.export import generate_audit_csv
from app.db.session import init_db
from app.db.repository import delete_all_documents

client = TestClient(app)


# ============================================================================
# TASK 1 TESTS: RECEIPT MODEL ROUTING
# ============================================================================
class TestReceiptRouting:
    def test_is_receipt_filename_variants(self):
        """Verify standard receipt filename variants route correctly."""
        assert is_receipt_filename("REC-003.pdf") is True
        assert is_receipt_filename("REC_006.pdf") is True
        assert is_receipt_filename("rec-101.png") is True
        assert is_receipt_filename("rec_404.jpg") is True
        assert is_receipt_filename("campus_receipt.pdf") is True
        assert is_receipt_filename("fee_receipt_term1.pdf") is True
        assert is_receipt_filename("REC-2026-999.PDF") is True

    def test_is_receipt_filename_invoices_return_false(self):
        """Verify invoice filenames are not recognized as receipts."""
        assert is_receipt_filename("INV-001.pdf") is False
        assert is_receipt_filename("inv_002.pdf") is False
        assert is_receipt_filename("invoice_supplies.pdf") is False
        assert is_receipt_filename("billing_statement.pdf") is False

    def test_determine_model_precedence(self):
        """Explicit preferred_model must take precedence over filename and document_type."""
        # preferred_model wins over filename
        assert determine_model("INV-001.pdf", preferred_model="prebuilt-receipt") == "prebuilt-receipt"
        assert determine_model("REC-003.pdf", preferred_model="prebuilt-invoice") == "prebuilt-invoice"

        # document_type takes precedence over filename
        assert determine_model("REC-003.pdf", document_type="invoice") == "prebuilt-invoice"
        assert determine_model("INV-001.pdf", document_type="receipt") == "prebuilt-receipt"

        # Filename heuristic when no explicit preference
        assert determine_model("REC-003.pdf") == "prebuilt-receipt"
        assert determine_model("REC_006.pdf") == "prebuilt-receipt"
        assert determine_model("INV-001.pdf") == "prebuilt-invoice"
        assert determine_model("INV-002.pdf") == "prebuilt-invoice"
        assert determine_model("random_doc.pdf") == "prebuilt-invoice"


# ============================================================================
# TASK 2 TESTS: DETERMINISTIC DATE PARSING & ACADEMIC TERM
# ============================================================================
class TestDateParsingAndAcademicTerm:
    @pytest.mark.parametrize(
        "date_input,expected_date",
        [
            ("2026-08-01", date(2026, 8, 1)),
            ("2026-12-31", date(2026, 12, 31)),
            ("2027-01-15", date(2027, 1, 15)),
            ("15 November 2026", date(2026, 11, 15)),
            ("15 Nov 2026", date(2026, 11, 15)),
            ("November 15, 2026", date(2026, 11, 15)),
            ("Nov 15, 2026", date(2026, 11, 15)),
            ("15/11/2026", date(2026, 11, 15)),
            ("11/15/2026", date(2026, 11, 15)),
            ("15-11-2026", date(2026, 11, 15)),
            ("2026/09/12", date(2026, 9, 12)),
        ],
    )
    def test_parse_iso_date_valid_formats(self, date_input, expected_date):
        """Verify deterministic parsing of all required date formats."""
        parsed = _parse_iso_date(date_input)
        assert parsed == expected_date

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "invalid_date",
            "99/99/9999",
            "2026-13-45",
            "",
            None,
            "not a date string",
        ],
    )
    def test_parse_iso_date_invalid_returns_none(self, invalid_input):
        """Invalid date strings must return None deterministically, never silently accepted."""
        assert _parse_iso_date(invalid_input) is None

    def test_extract_date_value_normalizes_to_iso(self):
        """_extract_date_value in extractor normalizes natural date strings to ISO YYYY-MM-DD."""
        assert _extract_date_value("15 November 2026") == "2026-11-15"
        assert _extract_date_value("Nov 15, 2026") == "2026-11-15"
        assert _extract_date_value("2026-08-01") == "2026-08-01"

    def test_academic_term_boundary_inclusivity(self):
        """Academic term start and end boundaries must be inclusive."""
        def make_doc_with_date(d_str: str) -> DocumentExtraction:
            return DocumentExtraction(
                file_name="test_term.pdf",
                file_hash="hash_term",
                model_used="prebuilt-invoice",
                document_type="invoice",
                invoice_date=ExtractedField(value=d_str, confidence=0.95, status=FieldStatus.EXTRACTED),
                total=ExtractedField(value="100.00", confidence=0.95, status=FieldStatus.EXTRACTED),
            )

        # Term boundaries: 2026-08-01 to 2026-12-31
        # 1. Exact start date (inclusive) -> Clean
        flag_start = validate_v04_outside_academic_term(make_doc_with_date("2026-08-01"))
        assert flag_start is None

        # 2. Exact end date (inclusive) -> Clean
        flag_end = validate_v04_outside_academic_term(make_doc_with_date("2026-12-31"))
        assert flag_end is None

        # 3. Inside term -> Clean
        flag_mid = validate_v04_outside_academic_term(make_doc_with_date("15 November 2026"))
        assert flag_mid is None

        # 4. Outside term (Post-term January 2027) -> Flagged V04
        flag_out = validate_v04_outside_academic_term(make_doc_with_date("2027-01-15"))
        assert flag_out is not None
        assert flag_out.rule_id == "V04"
        assert flag_out.severity == "MEDIUM"
        assert "2027-01-15" in flag_out.actual_value

        # 5. Outside term (Pre-term July 2026) -> Flagged V04
        flag_pre = validate_v04_outside_academic_term(make_doc_with_date("2026-07-31"))
        assert flag_pre is not None
        assert flag_pre.rule_id == "V04"


# ============================================================================
# TASK 4 TESTS: OCR CONFIDENCE HANDLING (<0.85, ==0.85, >0.85)
# ============================================================================
class TestOcrConfidenceHandling:
    def _create_doc_for_conf_test(
        self,
        vendor_conf=0.95,
        total_conf=0.95,
        total_status=FieldStatus.EXTRACTED,
        total_val="100.00",
    ) -> DocumentExtraction:
        return DocumentExtraction(
            file_name="conf_test.pdf",
            file_hash="hash_conf",
            model_used="prebuilt-invoice",
            document_type="invoice",
            vendor_name=ExtractedField(value="Vendor Inc", confidence=vendor_conf, status=FieldStatus.EXTRACTED),
            invoice_id=ExtractedField(value="INV-001", confidence=0.95, status=FieldStatus.EXTRACTED),
            invoice_date=ExtractedField(value="2026-09-10", confidence=0.95, status=FieldStatus.EXTRACTED),
            vendor_tax_id=ExtractedField(value="FAKE-GST-001", confidence=0.95, status=FieldStatus.EXTRACTED),
            total=ExtractedField(value=total_val, confidence=total_conf, status=total_status),
        )

    def test_confidence_below_threshold_triggers_warning(self):
        """Confidence < 0.85 (e.g. 0.84) triggers V05 warning with manual verification recommendation."""
        doc = self._create_doc_for_conf_test(total_conf=0.84)
        flags = validate_v05_low_confidence(doc, threshold=0.85)
        assert len(flags) == 1
        assert flags[0].rule_id == "V05"
        assert flags[0].field_name == "total"
        assert flags[0].severity == "WARNING"
        assert "84.0%" in flags[0].reason
        assert "Manual verification recommended" in flags[0].reason

    def test_confidence_equal_threshold_passes(self):
        """Confidence == 0.85 is considered acceptable and does NOT trigger V05."""
        doc = self._create_doc_for_conf_test(total_conf=0.85)
        flags = validate_v05_low_confidence(doc, threshold=0.85)
        assert len(flags) == 0

    def test_confidence_above_threshold_passes(self):
        """Confidence > 0.85 (e.g. 0.86, 0.98) does NOT trigger V05."""
        doc = self._create_doc_for_conf_test(total_conf=0.86)
        flags = validate_v05_low_confidence(doc, threshold=0.85)
        assert len(flags) == 0

    def test_missing_and_not_applicable_fields_do_not_trigger_v05(self):
        """Missing or NOT_APPLICABLE fields must never trigger low-confidence warnings."""
        doc = self._create_doc_for_conf_test(
            total_conf=None,
            total_status=FieldStatus.MISSING,
            total_val=None,
        )
        flags = validate_v05_low_confidence(doc, threshold=0.85)
        assert len(flags) == 0

        # Receipt tax_id is NOT_APPLICABLE
        receipt_doc = DocumentExtraction(
            file_name="REC-003.pdf",
            file_hash="hash_rec_003",
            model_used="prebuilt-receipt",
            document_type="receipt",
            vendor_name=ExtractedField(value="Institute", confidence=0.95, status=FieldStatus.EXTRACTED),
            invoice_date=ExtractedField(value="2026-11-15", confidence=0.95, status=FieldStatus.EXTRACTED),
            vendor_tax_id=ExtractedField(value=None, confidence=None, status=FieldStatus.NOT_APPLICABLE),
            total=ExtractedField(value="29000.00", confidence=0.95, status=FieldStatus.EXTRACTED),
        )
        r_flags = validate_v05_low_confidence(receipt_doc, threshold=0.85)
        assert len(r_flags) == 0


# ============================================================================
# TASK 5 TESTS: SECURITY HARDENING (UPLOAD SIZE LIMIT & CORS)
# ============================================================================
class TestSecurityHardening:
    def test_upload_rejection_exceeding_20mb(self):
        """Files exceeding 20 MB must be rejected with an understandable error without crashing."""
        # 21 MB payload
        oversized_data = b"0" * (21 * 1024 * 1024)
        response = client.post(
            "/api/audit/upload",
            files=[("files", ("oversized_file.pdf", oversized_data, "application/pdf"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful_extractions"] == 0
        assert data["failed_extractions"] == 1
        assert len(data["errors"]) == 1
        err_msg = data["errors"][0]["error"]
        assert "exceeds maximum allowed upload size of 20 MB" in err_msg

    def test_cors_configuration_allows_configured_and_restricts_wildcard(self):
        """Configured frontend origin is accepted, wildcard origins with credentials disallowed."""
        assert "*" not in settings.cors_origins_list
        assert "http://localhost:5173" in settings.cors_origins_list

        # Test preflight request from allowed origin
        res = client.options(
            "/api/audit/documents",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert res.headers.get("access-control-allow-credentials") == "true"

        # Preflight request from unauthorized origin
        res_bad = client.options(
            "/api/audit/documents",
            headers={
                "Origin": "http://unauthorized-malicious-domain.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res_bad.headers.get("access-control-allow-origin") != "http://unauthorized-malicious-domain.com"
        assert res_bad.headers.get("access-control-allow-origin") != "*"


# ============================================================================
# TASK 6 TESTS: AZURE ENDPOINT NORMALIZATION
# ============================================================================
class TestAzureEndpointNormalization:
    def test_canonical_endpoint_trailing_slash_removal(self):
        """Endpoint with trailing slashes is normalized canonically."""
        original = settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        try:
            settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = "https://my-resource.cognitiveservices.azure.com///"
            assert settings.canonical_azure_endpoint == "https://my-resource.cognitiveservices.azure.com"
        finally:
            settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = original


# ============================================================================
# TASK 3 & CSV EXPORT TESTS
# ============================================================================
class TestUnifiedDatasetAndCsvExport:
    def test_canonical_inr_samples_exist_and_ground_truth_matches(self):
        """Verify the 6 canonical INR PDFs exist and ground truth covers all 6."""
        samples_dir = Path(__file__).resolve().parent.parent / "synthetic_data" / "samples"
        pdf_names = sorted([f.name for f in samples_dir.glob("*.pdf")])
        expected_names = ["INV-001.pdf", "INV-002.pdf", "INV-004.pdf", "INV-005.pdf", "REC-003.pdf", "REC-006.pdf"]
        assert pdf_names == expected_names

        # Verify ground truth
        gt_path = Path(__file__).resolve().parent.parent / "synthetic_data" / "ground_truth.json"
        with open(gt_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        for name in expected_names:
            assert name in gt_data
            assert gt_data[name]["filename"] == name

    def test_csv_export_structure(self):
        """Verify CSV export includes extracted values, confidence scores, and plain-language flags."""
        sample_doc = DocumentExtraction(
            file_name="INV-001.pdf",
            file_hash="hash_csv_test",
            model_used="prebuilt-invoice",
            document_type="invoice",
            vendor_name=ExtractedField(value="Aster Supplies", confidence=0.98, status=FieldStatus.EXTRACTED),
            invoice_id=ExtractedField(value="INV-2026-001", confidence=0.95, status=FieldStatus.EXTRACTED),
            invoice_date=ExtractedField(value="2026-09-12", confidence=0.96, status=FieldStatus.EXTRACTED),
            vendor_tax_id=ExtractedField(value="FAKE-GST-001", confidence=0.99, status=FieldStatus.EXTRACTED),
            subtotal=ExtractedField(value="8300.00", confidence=0.95, status=FieldStatus.EXTRACTED),
            tax=ExtractedField(value="1494.00", confidence=0.95, status=FieldStatus.EXTRACTED),
            total=ExtractedField(value="9794.00", confidence=0.97, status=FieldStatus.EXTRACTED),
        )

        csv_bytes = generate_audit_csv([sample_doc])
        csv_text = csv_bytes.decode("utf-8")

        # Verify header columns
        assert "Document ID" in csv_text
        assert "File Name" in csv_text
        assert "Audit Status" in csv_text
        assert "Vendor Name" in csv_text
        assert "Total Amount" in csv_text
        assert "Total Confidence" in csv_text
        assert "Vendor Tax ID" in csv_text
        assert "Flag Details" in csv_text

        # Verify row content
        assert "INV-001.pdf" in csv_text
        assert "Aster Supplies" in csv_text
        assert "9794.00" in csv_text

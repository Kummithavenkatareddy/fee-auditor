import io
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    AnalyzeImageOptions,
    ImageData,
    TextCategory,
    ImageCategory,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, HttpResponseError

import pypdf
from pypdf.errors import PdfReadError, PdfStreamError
try:
    import pypdfium2
except Exception:
    pypdfium2 = None

from app.config import settings
from app.schemas.document import (
    ContentSafetyResult,
    ContentSafetyCategoryResult,
    ContentScreeningRejection,
)

logger = logging.getLogger("fee_auditor.content_safety")

STANDARD_CATEGORIES = ["Hate", "SelfHarm", "Sexual", "Violence"]


def _normalize_category_name(cat_val: Any) -> str:
    """Normalize Azure SDK category enum or string to canonical category name."""
    if hasattr(cat_val, "value"):
        return str(cat_val.value)
    name = str(cat_val)
    if "." in name:
        name = name.split(".")[-1]
    return name


class ContentSafetyService:
    """Pre-screening service powered by Azure AI Content Safety.

    Executes before Azure AI Document Intelligence extraction to reject
    harmful, sexually explicit, vulgar, hateful, violent, or inappropriate documents.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout: Optional[float] = None,
        failure_policy: Optional[str] = None,
    ):
        self.endpoint = (endpoint or settings.canonical_content_safety_endpoint).strip().rstrip("/")
        self.key = (key or settings.CONTENT_SAFETY_KEY).strip()
        self.enabled = settings.CONTENT_SAFETY_ENABLED if enabled is None else enabled
        self.timeout = settings.CONTENT_SAFETY_TIMEOUT if timeout is None else timeout
        self.failure_policy = (
            failure_policy or settings.CONTENT_SAFETY_FAILURE_POLICY
        ).strip().lower()

        self._client: Optional[ContentSafetyClient] = None
        if self.enabled and self.endpoint and self.key:
            try:
                self._client = ContentSafetyClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.key),
                )
            except Exception as e:
                logger.error(f"Failed to initialize Azure ContentSafetyClient: {e}")
                self._client = None

    @property
    def is_available(self) -> bool:
        """Check if Content Safety service is enabled and client initialized."""
        return self.enabled and self._client is not None

    def _extract_pdf_pages_text(self, file_bytes: bytes) -> Tuple[List[str], Optional[str]]:
        """Extract text per page from PDF bytes using pypdf.

        Returns (list_of_page_texts, error_message).
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                return [], "PDF document is password-protected or encrypted; unable to screen content."
            page_texts = []
            for idx, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                except Exception as e:
                    logger.warning(f"Error extracting text from PDF page {idx}: {e}")
                    page_texts.append("")
            return page_texts, None
        except (PdfReadError, PdfStreamError) as e:
            return [], f"Corrupt or unreadable PDF document: {e}"
        except Exception as e:
            return [], f"Failed to parse PDF document: {e}"

    def _render_pdf_pages_to_images(
        self, file_bytes: bytes, max_pages: int = 10
    ) -> Tuple[List[bytes], Optional[str]]:
        """Render PDF pages to JPEG bytes using pypdfium2, or fallback to embedded images if pypdfium2 is unavailable.

        Returns (list_of_image_bytes, error_message).
        """
        if pypdfium2 is not None:
            try:
                pdf = pypdfium2.PdfDocument(file_bytes)
                num_pages = len(pdf)
                pages_to_render = min(num_pages, max_pages)
                image_bytes_list: List[bytes] = []

                for i in range(pages_to_render):
                    page = pdf[i]
                    pil_image = page.render(scale=1.0).to_pil()
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    buf = io.BytesIO()
                    pil_image.save(buf, format="JPEG", quality=85)
                    image_bytes_list.append(buf.getvalue())
                return image_bytes_list, None
            except Exception as e:
                logger.warning(f"pypdfium2 page rendering error: {e}")

        # Fallback to pure-Python pypdf embedded image extraction
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            image_bytes_list: List[bytes] = []
            for page in reader.pages[:max_pages]:
                for img in getattr(page, "images", []):
                    image_bytes_list.append(img.data)
            return image_bytes_list, None
        except Exception as e:
            return [], f"Failed to render PDF pages to images: {e}"

    def _match_custom_terms(self, text: str) -> List[str]:
        """Check text against configured custom prohibited terms using exact word boundaries."""
        custom_terms = settings.custom_terms_list
        if not custom_terms or not text:
            return []

        matched: List[str] = []
        for term in custom_terms:
            if not term:
                continue
            # Use word boundaries so substrings inside legitimate words (like 'gross', 'penalties') aren't falsely matched
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(term)
        return matched

    def _analyze_text_chunk(self, text: str) -> Tuple[Dict[str, int], List[str], Optional[str]]:
        """Analyze a single text chunk with Azure AI Content Safety Analyze Text API.

        Returns (category_severities, matched_blocklists, error_message).
        """
        if not self._client:
            return {cat: 0 for cat in STANDARD_CATEGORIES}, [], "Client not initialized"

        try:
            blocklists = settings.blocklist_names_list or None
            options = AnalyzeTextOptions(
                text=text,
                blocklist_names=blocklists,
            )
            response = self._client.analyze_text(options, timeout=self.timeout)

            severities: Dict[str, int] = {}
            if hasattr(response, "categories_analysis") and response.categories_analysis:
                for item in response.categories_analysis:
                    cat_name = _normalize_category_name(item.category)
                    severities[cat_name] = int(item.severity)

            matched_blocklists: List[str] = []
            if hasattr(response, "blocklists_match") and response.blocklists_match:
                for match in response.blocklists_match:
                    name = getattr(match, "blocklist_name", "") or getattr(match, "blocklist_item_text", "")
                    if name:
                        matched_blocklists.append(str(name))

            return severities, matched_blocklists, None
        except Exception as e:
            logger.error(f"Azure Content Safety analyze_text call failed: {e}")
            return {}, [], str(e)

    def _analyze_image_bytes(self, image_bytes: bytes) -> Tuple[Dict[str, int], Optional[str]]:
        """Analyze image bytes with Azure AI Content Safety Analyze Image API.

        Returns (category_severities, error_message).
        """
        if not self._client:
            return {cat: 0 for cat in STANDARD_CATEGORIES}, "Client not initialized"

        try:
            options = AnalyzeImageOptions(
                image=ImageData(content=image_bytes),
            )
            response = self._client.analyze_image(options, timeout=self.timeout)

            severities: Dict[str, int] = {}
            if hasattr(response, "categories_analysis") and response.categories_analysis:
                for item in response.categories_analysis:
                    cat_name = _normalize_category_name(item.category)
                    severities[cat_name] = int(item.severity)

            return severities, None
        except Exception as e:
            logger.error(f"Azure Content Safety analyze_image call failed: {e}")
            return {}, str(e)

    def screen_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> ContentSafetyResult:
        """Screen an uploaded document (PDF or Image) before Document Intelligence extraction.

        Enforces:
        - Integrity validation
        - PDF embedded text extraction and screening
        - PDF page image rendering and screening
        - Multi-page severity aggregation
        - Custom prohibited term blocklist matching
        - Category-specific thresholds
        - Fail-closed / fail-open error handling
        """
        # If Content Safety is disabled or not configured
        if not self.enabled:
            return ContentSafetyResult(
                is_safe=True,
                status="skipped",
                action_taken="accepted",
                highest_severity=0,
                details="Content Safety screening is disabled by configuration.",
            )

        if not self._client:
            if self.failure_policy == "fail_open":
                logger.warning("Content Safety client unconfigured; failing open.")
                return ContentSafetyResult(
                    is_safe=True,
                    status="skipped",
                    action_taken="accepted",
                    highest_severity=0,
                    details="Content Safety client not configured; upload allowed under fail_open policy.",
                )
            return ContentSafetyResult(
                is_safe=False,
                status="failed",
                action_taken="error",
                highest_severity=0,
                rejection_reason="Content Safety service is unavailable and policy is fail_closed.",
                details="Azure AI Content Safety client credentials missing or invalid.",
            )

        # Check file size
        if len(file_bytes) > settings.max_upload_size_bytes:
            return ContentSafetyResult(
                is_safe=False,
                status="rejected",
                action_taken="rejected",
                highest_severity=6,
                rejection_reason=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        # Determine file type
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        is_pdf = ext == "pdf" or (content_type and "pdf" in content_type.lower())
        is_image = ext in ["png", "jpg", "jpeg"] or (
            content_type and any(t in content_type.lower() for t in ["image/png", "image/jpeg", "image/jpg"])
        )

        aggregated_severities: Dict[str, int] = {cat: 0 for cat in STANDARD_CATEGORIES}
        all_matched_terms: List[str] = []
        all_matched_blocklists: List[str] = []

        if is_pdf:
            # 1. Validate PDF integrity and extract embedded text
            page_texts, pdf_err = self._extract_pdf_pages_text(file_bytes)
            if pdf_err:
                logger.warning(f"PDF integrity/screening error for {filename}: {pdf_err}")
                if self.failure_policy == "fail_open" and "encrypted" not in pdf_err:
                    return ContentSafetyResult(
                        is_safe=True,
                        status="skipped",
                        action_taken="accepted",
                        highest_severity=0,
                        details=f"PDF parsing error bypassed under fail_open: {pdf_err}",
                    )
                return ContentSafetyResult(
                    is_safe=False,
                    status="failed",
                    action_taken="error",
                    highest_severity=0,
                    rejection_reason=pdf_err,
                    details="Document could not be safely inspected for inappropriate content.",
                )

            # 2. Check custom blocklist terms on text
            combined_text = "\n".join(page_texts)
            matched_custom = self._match_custom_terms(combined_text)
            if matched_custom:
                all_matched_terms.extend(matched_custom)
                logger.info(f"Custom prohibited term detected in {filename}")
                return ContentSafetyResult(
                    is_safe=False,
                    status="rejected",
                    action_taken="rejected",
                    highest_severity=4,
                    matched_custom_terms=all_matched_terms,
                    rejection_reason=f"Document contains prohibited term: '{matched_custom[0]}'",
                    details=f"Matched custom prohibited terms: {', '.join(matched_custom)}",
                )

            # 3. Screen text with Azure Content Safety (Analyze Text)
            if combined_text.strip():
                # Azure Content Safety text max limit is 10k chars; chunk if larger
                max_chunk_size = 9000
                chunks = [
                    combined_text[i : i + max_chunk_size]
                    for i in range(0, len(combined_text), max_chunk_size)
                ]
                for chunk in chunks:
                    text_severities, text_bl, text_err = self._analyze_text_chunk(chunk)
                    if text_err:
                        if self.failure_policy == "fail_closed":
                            return ContentSafetyResult(
                                is_safe=False,
                                status="failed",
                                action_taken="error",
                                highest_severity=0,
                                rejection_reason=f"Content Safety text analysis failed: {text_err}",
                                details="Screening service timeout or connection error under fail_closed policy.",
                            )
                        logger.warning(f"Text analysis error ignored under fail_open: {text_err}")
                    else:
                        for cat, sev in text_severities.items():
                            aggregated_severities[cat] = max(aggregated_severities.get(cat, 0), sev)
                        if text_bl:
                            all_matched_blocklists.extend(text_bl)

            # 4. Render PDF pages to images and screen with Azure Content Safety (Analyze Image)
            page_images, render_err = self._render_pdf_pages_to_images(file_bytes)
            if render_err:
                logger.warning(f"PDF page rendering error for {filename}: {render_err}")
                if self.failure_policy == "fail_closed":
                    return ContentSafetyResult(
                        is_safe=False,
                        status="failed",
                        action_taken="error",
                        highest_severity=0,
                        rejection_reason=render_err,
                        details="Document page rendering failed during Content Safety visual screening.",
                    )
            else:
                for page_idx, img_bytes in enumerate(page_images):
                    img_severities, img_err = self._analyze_image_bytes(img_bytes)
                    if img_err:
                        if self.failure_policy == "fail_closed":
                            return ContentSafetyResult(
                                is_safe=False,
                                status="failed",
                                action_taken="error",
                                highest_severity=0,
                                rejection_reason=f"Content Safety visual analysis failed on page {page_idx + 1}: {img_err}",
                                details="Visual screening service timeout or connection error under fail_closed policy.",
                            )
                        logger.warning(f"Image analysis error ignored under fail_open: {img_err}")
                    else:
                        for cat, sev in img_severities.items():
                            aggregated_severities[cat] = max(aggregated_severities.get(cat, 0), sev)

        elif is_image:
            # Analyze image directly
            img_severities, img_err = self._analyze_image_bytes(file_bytes)
            if img_err:
                if self.failure_policy == "fail_closed":
                    return ContentSafetyResult(
                        is_safe=False,
                        status="failed",
                        action_taken="error",
                        highest_severity=0,
                        rejection_reason=f"Content Safety image analysis failed: {img_err}",
                        details="Visual screening service timeout or connection error under fail_closed policy.",
                    )
                logger.warning(f"Image analysis error ignored under fail_open: {img_err}")
            else:
                for cat, sev in img_severities.items():
                    aggregated_severities[cat] = max(aggregated_severities.get(cat, 0), sev)

        else:
            # Unknown file type
            return ContentSafetyResult(
                is_safe=False,
                status="rejected",
                action_taken="rejected",
                highest_severity=0,
                rejection_reason=f"Unsupported document format '{ext}'. Only PDF, JPEG, and PNG files are supported.",
            )

        # 5. Check if any Azure blocklists matched
        if all_matched_blocklists:
            logger.info(f"Azure blocklist match detected in {filename}")
            return ContentSafetyResult(
                is_safe=False,
                status="rejected",
                action_taken="rejected",
                highest_severity=4,
                matched_blocklists=all_matched_blocklists,
                rejection_reason=f"Document contains prohibited term matching blocklist: {all_matched_blocklists[0]}",
                details=f"Matched Azure blocklists: {', '.join(all_matched_blocklists)}",
            )

        # 6. Evaluate aggregated severities against thresholds
        category_thresholds = settings.category_thresholds
        category_results: List[ContentSafetyCategoryResult] = []
        highest_severity = 0
        flagged_categories: List[Tuple[str, int, int]] = []

        for cat in STANDARD_CATEGORIES:
            sev = aggregated_severities.get(cat, 0)
            threshold = category_thresholds.get(cat, settings.CONTENT_SAFETY_DEFAULT_THRESHOLD)
            is_flagged = sev >= threshold
            highest_severity = max(highest_severity, sev)
            category_results.append(
                ContentSafetyCategoryResult(
                    category=cat,
                    severity=sev,
                    threshold=threshold,
                    flagged=is_flagged,
                )
            )
            if is_flagged:
                flagged_categories.append((cat, sev, threshold))

        if flagged_categories:
            # Sort by severity descending to report highest
            flagged_categories.sort(key=lambda x: x[1], reverse=True)
            top_cat, top_sev, top_thresh = flagged_categories[0]
            reason = (
                f"Document rejected by Content Safety: {top_cat} severity {top_sev} "
                f"meets or exceeds threshold {top_thresh}."
            )
            logger.info(f"Document {filename} REJECTED: {reason}")
            return ContentSafetyResult(
                is_safe=False,
                status="rejected",
                action_taken="rejected",
                highest_severity=highest_severity,
                categories=category_results,
                matched_custom_terms=all_matched_terms,
                matched_blocklists=all_matched_blocklists,
                rejection_reason=reason,
                details=f"Flagged categories: {', '.join(f'{c} (severity {s})' for c, s, _ in flagged_categories)}",
            )

        # 7. Document is safe!
        logger.info(f"Document {filename} passed Content Safety screening (highest severity: {highest_severity}).")
        return ContentSafetyResult(
            is_safe=True,
            status="passed",
            action_taken="accepted",
            highest_severity=highest_severity,
            categories=category_results,
            matched_custom_terms=all_matched_terms,
            matched_blocklists=all_matched_blocklists,
            details="All content categories within safe institutional audit thresholds.",
        )


# Singleton service instance
content_safety_service = ContentSafetyService()


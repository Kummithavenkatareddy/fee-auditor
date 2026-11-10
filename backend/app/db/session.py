import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager

from app.config import settings

DB_FILE = Path(settings.DATABASE_URL.replace("sqlite:///", ""))


def get_db_path() -> Path:
    raw_path = settings.DATABASE_URL.replace("sqlite:///", "")
    p = Path(raw_path)

    # In Vercel serverless functions, the root filesystem is read-only.
    # Store the SQLite database in the writable /tmp directory.
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp") / p.name
        if not tmp_db.exists():
            # Seed from committed repository database to preserve existing records
            candidates = [
                Path(__file__).resolve().parent.parent.parent / p.name,
                Path(__file__).resolve().parent.parent.parent / "backend" / p.name,
                Path(__file__).resolve().parent.parent / p.name,
            ]
            for candidate in candidates:
                if candidate.is_file():
                    try:
                        import shutil
                        shutil.copy2(candidate, tmp_db)
                        break
                    except Exception:
                        pass
        return tmp_db

    if not p.is_absolute():
        # Anchor relative database path to repository root for local development
        project_root = Path(__file__).resolve().parent.parent.parent
        return project_root / p.name
    return p


_db_initialized = False
_db_initializing = False


def ensure_db_initialized():
    global _db_initialized, _db_initializing
    if not _db_initialized and not _db_initializing:
        _db_initializing = True
        try:
            init_db()
            _db_initialized = True
        except Exception:
            pass
        finally:
            _db_initializing = False


@contextmanager
def get_db_connection():
    """Context manager for SQLite database connection with foreign keys enabled."""
    ensure_db_initialized()
    conn = sqlite3.connect(get_db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables, foreign keys, and indexes using canonical decimal strings (TEXT) for money."""
    db_path = get_db_path()
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Users table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                email_verified INTEGER DEFAULT 0,
                phone_verified INTEGER DEFAULT 0,
                display_name TEXT,
                identifier TEXT UNIQUE,
                full_name TEXT,
                is_verified INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                settings_json TEXT
            );
            """
        )

        # Seed system_default user row to satisfy foreign key constraints across documents and review_actions
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (id, identifier, email, phone, display_name, full_name, is_verified, password_hash, created_at)
            VALUES (
                'system_default',
                'auditor@university.edu',
                'auditor@university.edu',
                '+91 98765 43210',
                'System Auditor',
                'Institutional Auditor',
                1,
                'pbkdf2:system_default_protected_hash',
                '2026-08-01T00:00:00Z'
            );
            """
        )

        # 2. User sessions table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )

        # Legacy sessions alias / support
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )

        # 3. Documents table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256_hash TEXT NOT NULL,
                document_type TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                processing_status TEXT DEFAULT 'completed',
                audit_status TEXT DEFAULT 'clean',
                file_name TEXT,
                file_hash TEXT,
                model_used TEXT DEFAULT 'prebuilt-invoice',
                extraction_status TEXT DEFAULT 'succeeded',
                vendor_name TEXT,
                vendor_name_conf REAL,
                invoice_id TEXT,
                invoice_id_conf REAL,
                invoice_date TEXT,
                invoice_date_conf REAL,
                vendor_tax_id TEXT,
                vendor_tax_id_conf REAL,
                subtotal TEXT,
                subtotal_conf REAL,
                cgst TEXT,
                cgst_conf REAL,
                sgst TEXT,
                sgst_conf REAL,
                igst TEXT,
                igst_conf REAL,
                cess TEXT,
                cess_conf REAL,
                other_tax TEXT,
                other_tax_conf REAL,
                discounts TEXT,
                discounts_conf REAL,
                additional_charges TEXT,
                additional_charges_conf REAL,
                rounding_adjustment TEXT,
                rounding_adjustment_conf REAL,
                reconciliation_json TEXT,
                content_safety_status TEXT DEFAULT 'passed',
                content_safety_details TEXT,
                tax TEXT,
                tax_conf REAL,
                total TEXT,
                total_conf REAL,
                is_duplicate INTEGER DEFAULT 0,
                is_exact_duplicate INTEGER DEFAULT 0,
                is_business_duplicate INTEGER DEFAULT 0,
                manual_review_status TEXT DEFAULT 'pending',
                manual_review_notes TEXT,
                batch_id TEXT,
                created_at TEXT,
                audit_history TEXT,
                normalized_vendor_name TEXT,
                normalized_invoice_id TEXT,
                highest_severity TEXT,
                raw_azure_json TEXT,
                normalized_json TEXT,
                matched_document_id TEXT,
                matched_document_name TEXT,
                FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )

        # 4. Extractions table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                extracted_fields TEXT NOT NULL,
                confidence_data TEXT NOT NULL,
                raw_azure_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
            """
        )

        # 5. Audit runs table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_runs (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                academic_term_start TEXT,
                academic_term_end TEXT,
                rule_version TEXT NOT NULL DEFAULT 'V01-V05-v1.0',
                audit_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
            """
        )

        # 6. Validation flags table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_run_id TEXT,
                document_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                target_field TEXT,
                reason TEXT NOT NULL,
                expected_value TEXT,
                actual_value TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (audit_run_id) REFERENCES audit_runs (id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
            """
        )

        # Legacy audit_flags table support
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                field_name TEXT,
                reason TEXT NOT NULL,
                expected_value TEXT,
                actual_value TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
            """
        )

        # 7. Review actions table (Phase 2 canonical entity)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS review_actions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                reviewer_user_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                justification TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
                FOREIGN KEY (reviewer_user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )

        # 8. Line items table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                item_index INTEGER DEFAULT 0,
                description TEXT,
                quantity TEXT,
                unit_price TEXT,
                amount TEXT,
                confidence REAL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
            """
        )

        # 9. Verification codes table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # 10. Content Safety Events table (audit trail for screened documents)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS content_safety_events (
                id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                detected_category TEXT,
                severity INTEGER DEFAULT 0,
                action_taken TEXT NOT NULL,
                rejection_reason TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )

        # Safe Column Migrations for Users Table
        cursor.execute("PRAGMA table_info(users);")
        user_cols = {row[1] for row in cursor.fetchall()}
        if "email_verified" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0;")
        if "phone_verified" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN phone_verified INTEGER DEFAULT 0;")
        if "display_name" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN display_name TEXT;")
        if "identifier" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN identifier TEXT;")
        if "full_name" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT;")
        if "is_verified" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0;")
        if "settings_json" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN settings_json TEXT;")

        # Safe Column Migrations for Documents Table
        cursor.execute("PRAGMA table_info(documents);")
        doc_cols = {row[1] for row in cursor.fetchall()}
        if "owner_user_id" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN owner_user_id TEXT;")
        if "original_filename" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN original_filename TEXT;")
        if "storage_key" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN storage_key TEXT;")
        if "content_type" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN content_type TEXT;")
        if "file_size" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN file_size INTEGER;")
        if "sha256_hash" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN sha256_hash TEXT;")
        if "uploaded_at" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN uploaded_at TEXT;")
        if "processing_status" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN processing_status TEXT DEFAULT 'completed';")
        if "extraction_status" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN extraction_status TEXT DEFAULT 'succeeded';")
        if "audit_history" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN audit_history TEXT;")
        if "normalized_vendor_name" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN normalized_vendor_name TEXT;")
        if "normalized_invoice_id" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN normalized_invoice_id TEXT;")
        if "highest_severity" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN highest_severity TEXT;")
        if "matched_document_id" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN matched_document_id TEXT;")
        if "matched_document_name" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN matched_document_name TEXT;")
        if "cgst" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN cgst TEXT;")
        if "cgst_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN cgst_conf REAL;")
        if "sgst" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN sgst TEXT;")
        if "sgst_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN sgst_conf REAL;")
        if "igst" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN igst TEXT;")
        if "igst_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN igst_conf REAL;")
        if "cess" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN cess TEXT;")
        if "cess_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN cess_conf REAL;")
        if "other_tax" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN other_tax TEXT;")
        if "other_tax_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN other_tax_conf REAL;")
        if "discounts" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN discounts TEXT;")
        if "discounts_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN discounts_conf REAL;")
        if "additional_charges" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN additional_charges TEXT;")
        if "additional_charges_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN additional_charges_conf REAL;")
        if "rounding_adjustment" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN rounding_adjustment TEXT;")
        if "rounding_adjustment_conf" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN rounding_adjustment_conf REAL;")
        if "reconciliation_json" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN reconciliation_json TEXT;")
        if "content_safety_status" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN content_safety_status TEXT DEFAULT 'passed';")
        if "content_safety_details" not in doc_cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN content_safety_details TEXT;")

        cursor.execute("PRAGMA table_info(audit_flags);")
        existing_flag_cols = {row[1] for row in cursor.fetchall()}
        if "created_at" not in existing_flag_cols:
            cursor.execute("ALTER TABLE audit_flags ADD COLUMN created_at TEXT;")

        # Indexes for fast lookup, deduplication, and strict multi-user isolation
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_identifier ON users (identifier);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions (token_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_owner ON documents (owner_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON documents (sha256_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_owner_hash ON documents (owner_user_id, sha256_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_business ON documents (vendor_name, invoice_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON documents (audit_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_doc ON extractions (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_runs_doc ON audit_runs (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flags_run ON validation_flags (audit_run_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flags_doc ON validation_flags (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_doc ON review_actions (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_doc ON line_items (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legacy_flags_doc ON audit_flags (document_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legacy_session_token ON sessions (token);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cs_owner ON content_safety_events (owner_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cs_hash ON content_safety_events (sha256_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cs_status ON content_safety_events (status);")

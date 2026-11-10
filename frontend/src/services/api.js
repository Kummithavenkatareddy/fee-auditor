/**
 * Centralized API service layer for Fee Receipt & Invoice Auditor.
 * Integrates directly with FastAPI backend endpoints under /api.
 * Manages Bearer session tokens and multi-user requests.
 */

function getApiBase() {
  const envUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE;
  if (!envUrl) {
    return '/api';
  }
  const clean = envUrl.trim().replace(/\/+$/, '');
  return clean.endsWith('/api') ? clean : `${clean}/api`;
}

export const API_BASE = getApiBase();

export function getAuthToken() {
  return localStorage.getItem('fee_auditor_token');
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('fee_auditor_token', token);
  } else {
    localStorage.removeItem('fee_auditor_token');
  }
}

function getAuthHeaders(extraHeaders = {}) {
  const token = getAuthToken();
  const headers = { ...extraHeaders };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Handle API responses with standardized error extraction and session expiration handling.
 */
async function handleResponse(res, defaultErrorMsg = 'API request failed') {
  if (res.status === 401) {
    setAuthToken(null);
  }
  if (!res.ok) {
    let errorDetail = defaultErrorMsg;
    try {
      const data = await res.json();
      errorDetail = data.detail || data.message || defaultErrorMsg;
    } catch {
      errorDetail = `${defaultErrorMsg} (HTTP ${res.status})`;
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

/**
 * Check backend health status and active services.
 */
export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { credentials: 'include' });
    return await handleResponse(res, 'Health check failed');
  } catch (err) {
    console.warn('Health check unreachable:', err.message);
    return { status: 'offline', version: 'unknown' };
  }
}

/**
 * Fetch dashboard summary metrics.
 */
export async function fetchSummary() {
  const res = await fetch(`${API_BASE}/audit/summary`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to fetch audit summary metrics');
}

/**
 * Fetch all extracted and validated documents with optional status filter.
 * @param {string|null} status - 'clean', 'flagged', or 'reviewed'
 */
export async function fetchDocuments(status = null) {
  const url = status && status !== 'all'
    ? `${API_BASE}/audit/documents?status=${encodeURIComponent(status)}`
    : `${API_BASE}/audit/documents`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to fetch document ledger');
}

/**
 * Fetch complete document detail by ID, including line items and raw Azure JSON.
 * @param {string} id - Document ID
 */
export async function fetchDocument(id) {
  if (!id) throw new Error('Document ID is required');
  const res = await fetch(`${API_BASE}/audit/documents/${encodeURIComponent(id)}`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, `Failed to fetch document details for ID: ${id}`);
}

/**
 * Get direct URL to document file preview / download with query token for cross-domain auth.
 */
export function getDocumentFileUrl(id) {
  const token = getAuthToken();
  const base = `${API_BASE}/audit/documents/${encodeURIComponent(id)}/file`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/**
 * Delete a single document.
 */
export async function deleteDocument(id) {
  if (!id) throw new Error('Document ID is required');
  const res = await fetch(`${API_BASE}/audit/documents/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, `Failed to delete document: ${id}`);
}

/**
 * Bulk delete documents.
 */
export async function bulkDeleteDocuments(documentIds) {
  if (!documentIds || documentIds.length === 0) {
    return { deleted_count: 0 };
  }
  const res = await fetch(`${API_BASE}/audit/documents/bulk-delete`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ document_ids: documentIds }),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to bulk delete documents');
}

/**
 * Upload a batch of 1 or more documents (PDF, PNG, JPEG).
 * Note: Never set Content-Type header manually when sending FormData.
 * @param {File[]} files - Array of File objects
 * @param {string|null} preferredModel - 'prebuilt-invoice' | 'prebuilt-receipt' | null
 */
export async function uploadBatch(files, preferredModel = null) {
  if (!files || files.length === 0) {
    throw new Error('Please select at least one document to upload.');
  }

  // Pre-flight validation: check serverless payload constraint (4.5 MB)
  const totalSizeBytes = Array.from(files).reduce((acc, f) => acc + (f.size || 0), 0);
  if (totalSizeBytes > 4.5 * 1024 * 1024) {
    throw new Error(
      `Total batch payload size (${(totalSizeBytes / (1024 * 1024)).toFixed(1)} MB) exceeds the 4.5 MB serverless limit. Please upload documents in smaller batches or individually.`
    );
  }

  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  if (preferredModel && preferredModel !== 'auto') {
    formData.append('preferred_model', preferredModel);
  }

  try {
    const res = await fetch(`${API_BASE}/audit/upload`, {
      method: 'POST',
      headers: getAuthHeaders(), // Will only attach Authorization header, not Content-Type!
      body: formData,
      credentials: 'include',
    });

    return await handleResponse(res, 'Batch upload processing failed');
  } catch (err) {
    console.error('[UploadService] Batch upload network/processing failure:', err);
    if (err.name === 'TypeError' && err.message.toLowerCase().includes('failed to fetch')) {
      throw new Error(
        'Server connection error or timeout (Failed to fetch). Document processing with Azure AI Content Safety and Document Intelligence may have exceeded the execution limit, or the network was interrupted. Please retry with a single document.'
      );
    }
    throw err;
  }
}

/**
 * Re-run deterministic validation rules on an existing document.
 * @param {string} id - Document ID
 */
export async function revalidateDocument(id) {
  if (!id) throw new Error('Document ID is required');
  const res = await fetch(`${API_BASE}/audit/documents/${encodeURIComponent(id)}/revalidate`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, `Failed to re-validate document: ${id}`);
}

/**
 * Update manual reviewer status ('approved' | 'rejected' | 'pending') and notes.
 * @param {string} id - Document ID
 * @param {'approved'|'rejected'|'pending'} status - Review status
 * @param {string} notes - Auditor notes
 */
export async function updateManualReview(id, status, notes = '') {
  if (!id) throw new Error('Document ID is required');
  const res = await fetch(`${API_BASE}/audit/documents/${encodeURIComponent(id)}/review`, {
    method: 'PATCH',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ manual_review_status: status, notes }),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to save manual review update');
}

/**
 * Direct URL for downloading the audit CSV with query token for cross-domain auth.
 */
export function getExportCsvUrl() {
  const token = getAuthToken();
  const base = `${API_BASE}/audit/export/csv`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/**
 * Download CSV file directly through browser blob trigger with error checking.
 */
export async function downloadAuditCsv() {
  const res = await fetch(`${API_BASE}/audit/export/csv`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`CSV export failed (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `fee_auditor_ledger_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(downloadUrl);
  a.remove();
}

/**
 * Reset database records for testing purposes.
 */
export async function resetDatabase() {
  const res = await fetch(`${API_BASE}/audit/reset`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to reset audit database');
}

/**
 * Retrieve Content Safety screening and rejection events log.
 */
export async function fetchContentSafetyEvents() {
  const res = await fetch(`${API_BASE}/audit/content-safety-events`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to fetch content safety events');
}

// =========================================================================
// Authentication & User Profile API Calls
// =========================================================================

export async function registerApi(identifier, password, fullName = '') {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identifier,
      password,
      full_name: fullName,
    }),
    credentials: 'include',
  });
  return handleResponse(res, 'Registration failed');
}

export async function verifyApi(identifier, code) {
  const res = await fetch(`${API_BASE}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, code }),
    credentials: 'include',
  });
  const data = await handleResponse(res, 'Verification failed');
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function loginApi(identifier, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, password }),
    credentials: 'include',
  });
  const data = await handleResponse(res, 'Login failed');
  if (data?.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function logoutApi() {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
    });
  } catch (err) {
    console.warn('Logout endpoint error:', err);
  } finally {
    setAuthToken(null);
  }
}

export async function fetchMeApi() {
  const token = getAuthToken();
  if (!token) return null;
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!res.ok) {
    setAuthToken(null);
    return null;
  }
  return res.json();
}

export async function forgotPasswordApi(identifier) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier }),
    credentials: 'include',
  });
  return handleResponse(res, 'Password reset request failed');
}

export async function resetPasswordApi(identifier, code, newPassword) {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, code, new_password: newPassword }),
    credentials: 'include',
  });
  return handleResponse(res, 'Password reset failed');
}

export async function updateProfileApi(fullName, termPreference) {
  const res = await fetch(`${API_BASE}/users/profile`, {
    method: 'PATCH',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      full_name: fullName,
      term_preference: termPreference,
    }),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to update profile');
}

export async function changePasswordApi(currentPassword, newPassword) {
  const res = await fetch(`${API_BASE}/users/change-password`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
    credentials: 'include',
  });
  return handleResponse(res, 'Failed to change password');
}

export async function resetMyDataApi(password, confirmationPhrase = 'RESET') {
  const res = await fetch(`${API_BASE}/users/reset-data`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      password,
      confirmation_phrase: confirmationPhrase,
    }),
    credentials: 'include',
  });
  return handleResponse(res, 'Reset My Data operation failed');
}

export async function deleteAccountApi(password, confirmationPhrase = 'DELETE') {
  const res = await fetch(`${API_BASE}/users/account`, {
    method: 'DELETE',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      password,
      confirmation_phrase: confirmationPhrase,
    }),
    credentials: 'include',
  });
  const data = await handleResponse(res, 'Delete Account operation failed');
  setAuthToken(null);
  return data;
}

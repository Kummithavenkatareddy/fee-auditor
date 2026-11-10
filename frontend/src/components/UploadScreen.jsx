import React, { useState, useRef } from 'react';
import { uploadBatch, fetchDocument } from '../services/api';

export default function UploadScreen({ onUploadComplete, onSelectDoc, onNavigateTab }) {
  const [currentStage, setCurrentStage] = useState(1); // 1: Select, 2: Review Staged, 3: Ingestion
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [preferredModel, setPreferredModel] = useState('auto');
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [uploadResult, setUploadResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const fileInputRef = useRef(null);

  const MAX_FILE_SIZE = 4.5 * 1024 * 1024; // 4.5 MB serverless upload limit
  const validExtensions = ['.pdf', '.png', '.jpg', '.jpeg'];

  const addFiles = (files) => {
    setErrorMsg(null);
    const added = [];
    const oversized = [];
    const invalidType = [];

    Array.from(files).forEach((file) => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!validExtensions.includes(ext)) {
        invalidType.push(file.name);
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        oversized.push(file.name);
        return;
      }
      if (!selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
        added.push(file);
      }
    });

    if (oversized.length > 0) {
      setErrorMsg(`Files exceed 4.5 MB serverless limit: ${oversized.join(', ')}. Please use files under 4.5 MB.`);
    } else if (invalidType.length > 0) {
      setErrorMsg(`Unsupported files skipped: ${invalidType.join(', ')}. Use PDF, PNG, or JPEG.`);
    }

    if (added.length > 0) {
      setSelectedFiles((prev) => [...prev, ...added]);
      setCurrentStage(2); // Automatically advance to Stage 2 to review staged files
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
  };

  const removeFile = (index) => {
    const updated = selectedFiles.filter((_, i) => i !== index);
    setSelectedFiles(updated);
    if (updated.length === 0) {
      setCurrentStage(1);
    }
  };

  const handleStartProcessing = async () => {
    if (selectedFiles.length === 0) {
      setErrorMsg('Please select at least 1 file.');
      return;
    }

    setCurrentStage(3);
    setIsProcessing(true);
    setProgressPct(20);
    setStatusMessage(`Transferring ${selectedFiles.length} file(s) to persistent storage...`);
    setErrorMsg(null);
    setUploadResult(null);

    try {
      setProgressPct(50);
      setStatusMessage('Azure AI Document Intelligence extracting financial schedules...');

      const modelParam = preferredModel === 'auto' ? null : preferredModel;
      const res = await uploadBatch(selectedFiles, modelParam);

      setProgressPct(85);
      setStatusMessage('Applying deterministic financial rules V01–V05...');

      setTimeout(() => {
        setProgressPct(100);
        setIsProcessing(false);
        setUploadResult(res);
        setSelectedFiles([]);
        if (onUploadComplete) onUploadComplete();
      }, 500);
    } catch (err) {
      setIsProcessing(false);
      setErrorMsg(err.message || 'Batch upload failed');
    }
  };

  const handleOpenExisting = async (docId) => {
    try {
      const doc = await fetchDocument(docId);
      if (doc && onSelectDoc) {
        onSelectDoc(doc);
      }
    } catch (err) {
      setErrorMsg(`Could not open existing document: ${err.message}`);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Upload &amp; Process Documents</h1>
          <p className="text-xs text-slate-500 mt-1">
            Batch ingest fee receipts and vendor invoices into your persistent library with automated validation.
          </p>
        </div>
      </div>

      {/* Stepper (3 Stages) */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div
          onClick={() => !isProcessing && setCurrentStage(1)}
          className={`p-3 rounded-lg border transition-all cursor-pointer ${
            currentStage === 1
              ? 'bg-blue-50 border-blue-600 text-blue-900 font-bold shadow-2xs'
              : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center justify-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">1</span>
            <span>Select Files</span>
          </div>
        </div>

        <div
          onClick={() => !isProcessing && selectedFiles.length > 0 && setCurrentStage(2)}
          className={`p-3 rounded-lg border transition-all ${
            selectedFiles.length === 0 ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
          } ${
            currentStage === 2
              ? 'bg-blue-50 border-blue-600 text-blue-900 font-bold shadow-2xs'
              : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center justify-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">2</span>
            <span>Review Staged ({selectedFiles.length})</span>
          </div>
        </div>

        <div
          className={`p-3 rounded-lg border transition-all ${
            currentStage === 3
              ? 'bg-blue-50 border-blue-600 text-blue-900 font-bold shadow-2xs'
              : 'bg-white border-slate-200 text-slate-500'
          }`}
        >
          <div className="flex items-center justify-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">3</span>
            <span>Process &amp; Verify</span>
          </div>
        </div>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-rose-600">error</span>
          <span>{errorMsg}</span>
        </div>
      )}

      {/* STAGE 1: File Selection Dropzone */}
      {currentStage === 1 && (
        <div className="space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); }}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-300 hover:border-blue-500 hover:bg-blue-50/20 rounded-2xl p-12 text-center cursor-pointer transition-all bg-white"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileInput}
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
            />
            <div className="w-14 h-14 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
              <span className="material-symbols-outlined text-[32px]">cloud_upload</span>
            </div>
            <h3 className="text-base font-bold text-slate-900">
              Drag &amp; drop document files here, or click to browse
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
              Supports <strong>PDF, PNG, and JPEG</strong>. Maximum file size: <strong>20 MB</strong> per file.
            </p>
          </div>
        </div>
      )}

      {/* STAGE 2: Review Staged Files */}
      {currentStage === 2 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Stage 2: Staged Files Review</h2>
              <p className="text-xs text-slate-500">Confirm documents and optional model routing preference before ingestion.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 hover:bg-slate-50 font-medium"
              >
                + Add More
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileInput}
                multiple
                accept=".pdf,.png,.jpg,.jpeg"
                className="hidden"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
            <span className="font-semibold text-slate-700">Azure Model Preference:</span>
            <select
              value={preferredModel}
              onChange={(e) => setPreferredModel(e.target.value)}
              className="bg-white border border-slate-300 rounded px-2.5 py-1 text-xs focus:outline-none"
            >
              <option value="auto">Auto-detect from filename &amp; layout</option>
              <option value="prebuilt-invoice">Force prebuilt-invoice</option>
              <option value="prebuilt-receipt">Force prebuilt-receipt</option>
            </select>
          </div>

          {/* Staged files table */}
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-600 font-semibold text-[11px] uppercase border-b border-slate-200">
                  <th className="py-2.5 px-3">File Name</th>
                  <th className="py-2.5 px-3">Size</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {selectedFiles.map((f, idx) => (
                  <tr key={idx} className="h-10 hover:bg-slate-50">
                    <td className="py-2 px-3 font-mono font-medium text-slate-800 flex items-center gap-2">
                      <span className="material-symbols-outlined text-[16px] text-blue-600">description</span>
                      <span className="truncate max-w-sm">{f.name}</span>
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-500">
                      {(f.size / (1024 * 1024)).toFixed(2)} MB
                    </td>
                    <td className="py-2 px-3 text-slate-600 uppercase text-[10px] font-mono">
                      {f.name.split('.').pop()}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => removeFile(idx)}
                        className="text-slate-400 hover:text-rose-600 p-1"
                        title="Remove"
                      >
                        <span className="material-symbols-outlined text-[16px]">delete</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setSelectedFiles([])}
              className="text-xs text-slate-500 hover:text-slate-800"
            >
              Clear All Staged
            </button>

            <button
              onClick={handleStartProcessing}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">play_arrow</span>
              <span>Process Batch ({selectedFiles.length} Documents)</span>
            </button>
          </div>
        </div>
      )}

      {/* STAGE 3: Processing & Results */}
      {currentStage === 3 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-5">
          {isProcessing ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-4 max-w-md mx-auto text-center">
              <div className="w-12 h-12 border-3 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Processing Document Batch</h3>
                <p className="text-xs text-slate-500 mt-1">{statusMessage}</p>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div
                  style={{ width: `${progressPct}%` }}
                  className="bg-blue-600 h-full rounded-full transition-all duration-300"
                ></div>
              </div>
            </div>
          ) : uploadResult ? (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-xl flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                    <span className="material-symbols-outlined text-[24px]">check</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-sm">Batch Ingestion Complete</h3>
                    <p className="text-xs text-emerald-700">
                      Successfully processed <strong>{uploadResult.successful_extractions}</strong> document(s)
                      {uploadResult.duplicate_files > 0 && (
                        <span className="text-amber-800 font-semibold ml-1">
                          • {uploadResult.duplicate_files} exact duplicate(s)
                        </span>
                      )}
                      {uploadResult.rejected_by_content_safety > 0 && (
                        <span className="text-rose-800 font-semibold ml-1">
                          • {uploadResult.rejected_by_content_safety} rejected by Content Safety
                        </span>
                      )}
                      {uploadResult.screening_failed > 0 && (
                        <span className="text-amber-800 font-semibold ml-1">
                          • {uploadResult.screening_failed} screening failure(s)
                        </span>
                      )}
                      {uploadResult.failed_extractions > 0 && (
                        <span className="text-rose-700 font-semibold ml-1">
                          • {uploadResult.failed_extractions} error(s)
                        </span>
                      )}
                      {' '}of {uploadResult.total_files} total.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {onNavigateTab && (
                    <button
                      onClick={() => onNavigateTab('documents')}
                      className="px-3.5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold shadow-2xs transition-colors"
                    >
                      View in Library
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setCurrentStage(1);
                      setUploadResult(null);
                    }}
                    className="px-3.5 py-2 bg-white text-emerald-800 border border-emerald-300 rounded-lg text-xs font-semibold hover:bg-emerald-50"
                  >
                    Upload Another Batch
                  </button>
                </div>
              </div>

              {/* Content Safety Alerts Banner */}
              {uploadResult.rejected_documents && uploadResult.rejected_documents.length > 0 && (
                <div className="p-4 bg-rose-50 border border-rose-200 text-rose-900 rounded-xl space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[20px] text-rose-600">shield_with_heart</span>
                    <span className="font-bold text-sm">
                      Azure AI Content Safety Intervention ({uploadResult.rejected_documents.length})
                    </span>
                  </div>
                  <p className="text-xs text-rose-700">
                    The following document(s) failed pre-screening and were halted before Document Intelligence extraction. Unsafe documents do not enter persistent accounting records.
                  </p>
                  <div className="divide-y divide-rose-200/60 bg-white/70 rounded-lg border border-rose-200 overflow-hidden text-xs">
                    {uploadResult.rejected_documents.map((rej, idx) => (
                      <div key={idx} className="p-3 flex items-start justify-between gap-3 flex-wrap">
                        <div className="space-y-1 max-w-xl">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-rose-950">{rej.file_name}</span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                rej.status === 'rejected'
                                  ? 'bg-rose-600 text-white'
                                  : 'bg-amber-600 text-white'
                              }`}
                            >
                              {rej.status === 'rejected' ? 'REJECTED' : 'SCREENING FAILED'}
                            </span>
                            {rej.detected_category && (
                              <span className="px-1.5 py-0.5 bg-rose-100 text-rose-800 rounded text-[10px] font-medium">
                                Category: {rej.detected_category}
                              </span>
                            )}
                            {rej.severity > 0 && (
                              <span className="px-1.5 py-0.5 bg-rose-200 text-rose-900 rounded text-[10px] font-semibold">
                                Severity: {rej.severity} / 6
                              </span>
                            )}
                          </div>
                          <div className="text-rose-800 font-medium">{rej.reason}</div>
                          {rej.error_message && (
                            <div className="text-[11px] text-rose-600 font-mono">{rej.error_message}</div>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 italic shrink-0">
                          Extraction Prevented
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Errors banner if any */}
              {uploadResult.errors && uploadResult.errors.length > 0 && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg text-xs space-y-1">
                  <div className="font-bold flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] text-rose-600">error</span>
                    <span>Upload Issues Detected ({uploadResult.errors.length})</span>
                  </div>
                  {uploadResult.errors.map((err, idx) => (
                    <div key={idx} className="ml-5">
                      <span className="font-mono font-semibold">{err.file_name}:</span> {err.error}
                    </div>
                  ))}
                </div>
              )}

              {/* Ingestion & Duplicate Results Table */}
              {((uploadResult.documents && uploadResult.documents.length > 0) || (uploadResult.duplicates && uploadResult.duplicates.length > 0)) && (
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100 text-slate-600 font-semibold uppercase text-[10px]">
                        <th className="py-2 px-3">File Name</th>
                        <th className="py-2 px-3">Vendor / Payee / Reference</th>
                        <th className="py-2 px-3 text-right">Total / Status</th>
                        <th className="py-2 px-3 text-center">Audit Status</th>
                        <th className="py-2 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {/* Newly processed documents */}
                      {uploadResult.documents && uploadResult.documents.map((d) => (
                        <tr key={d.id} className="h-10 hover:bg-slate-50">
                          <td className="py-2 px-3 font-mono font-medium text-blue-700">
                            <div className="flex items-center gap-1.5">
                              <span
                                className="material-symbols-outlined text-[15px] text-emerald-600 shrink-0"
                                title="Passed Azure AI Content Safety pre-screening"
                              >
                                verified_user
                              </span>
                              <span className="truncate">{d.file_name}</span>
                            </div>
                          </td>
                          <td className="py-2 px-3">{d.vendor_name?.value || '—'}</td>
                          <td className="py-2 px-3 text-right font-mono font-bold">
                            ₹{parseFloat(d.total?.value || 0).toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                d.audit_status === 'clean'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              {d.audit_status.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button
                              onClick={() => onSelectDoc && onSelectDoc(d)}
                              className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-0.5 ml-auto"
                            >
                              <span>Open Workspace</span>
                              <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                            </button>
                          </td>
                        </tr>
                      ))}

                      {/* Level 1 Exact Duplicates */}
                      {uploadResult.duplicates && uploadResult.duplicates.map((dup, idx) => (
                        <tr key={`dup-${idx}`} className="h-10 bg-amber-50/50 hover:bg-amber-50/80 border-t border-amber-100">
                          <td className="py-2 px-3 font-mono font-medium text-amber-900">
                            {dup.filename}
                          </td>
                          <td className="py-2 px-3 text-slate-600">
                            <div className="flex items-center gap-1">
                              <span className="text-[11px] text-amber-700 font-medium">Matches:</span>
                              <span className="font-mono text-slate-800 font-semibold">{dup.existing_file_name}</span>
                            </div>
                          </td>
                          <td className="py-2 px-3 text-right font-mono text-[11px] text-slate-500">
                            Original: <span className={`font-bold ${dup.audit_status === 'clean' ? 'text-emerald-700' : 'text-rose-700'}`}>{dup.audit_status.toUpperCase()}</span>
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                              DUPLICATE
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button
                              onClick={() => handleOpenExisting(dup.existing_document_id)}
                              className="text-xs text-amber-900 hover:text-amber-950 font-medium flex items-center gap-0.5 ml-auto px-2 py-1 rounded bg-amber-200/60 hover:bg-amber-200 border border-amber-300 transition-colors"
                              title="Open existing document in workspace"
                            >
                              <span>Open Existing Document</span>
                              <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

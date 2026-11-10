import React, { useState, useRef } from 'react';
import { Upload, FileUp, X, Sparkles, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { uploadBatch } from '../services/api';

export default function BatchUploader({ onBatchComplete }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [modelType, setModelType] = useState('auto');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      const filesArray = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const removeFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setUploadStatus(null);

    try {
      const res = await uploadBatch(selectedFiles, modelType);
      setUploadStatus({
        type: 'success',
        message: `Successfully processed ${res.successful_extractions} documents with Azure Document Intelligence (${res.failed_extractions} errors).`,
      });
      setSelectedFiles([]);
      if (onBatchComplete) onBatchComplete();
    } catch (err) {
      setUploadStatus({
        type: 'error',
        message: err.message || 'Batch upload failed.',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-card">
      <div className="upload-header">
        <div>
          <h2 className="upload-title">
            <Upload size={20} color="#2563eb" /> Batch Document Ingestion
          </h2>
          <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '2px' }}>
            Upload batches of fee receipts and invoices (PDF, PNG, JPEG). Requirement: Batch of at least 5 documents.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              fontSize: '0.82rem',
              fontWeight: 500,
              color: '#334155',
              background: '#fff',
            }}
          >
            <option value="auto">Auto-detect (Invoice / Receipt)</option>
            <option value="prebuilt-invoice">Force: prebuilt-invoice</option>
            <option value="prebuilt-receipt">Force: prebuilt-receipt</option>
          </select>
        </div>
      </div>

      {/* Drag & Drop Area */}
      <div
        className={`dropzone ${isDragging ? 'drag-active' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          multiple
          accept=".pdf,.png,.jpg,.jpeg"
          style={{ display: 'none' }}
        />
        <FileUp className="dropzone-icon" />
        <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: '#1e293b' }}>
          Click to browse or drag and drop invoice files here
        </h3>
        <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '4px' }}>
          Supports batch uploads (5+ documents). PDF, PNG, JPG accepted.
        </p>
      </div>

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>
              Selected Documents ({selectedFiles.length})
              {selectedFiles.length >= 5 ? (
                <span style={{ color: '#059669', marginLeft: '8px', fontSize: '0.78rem' }}>
                  ✓ Meets 5+ batch requirement
                </span>
              ) : (
                <span style={{ color: '#d97706', marginLeft: '8px', fontSize: '0.78rem' }}>
                  (Select at least 5 documents for full batch audit)
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={() => setSelectedFiles([])}
              style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '0.78rem', cursor: 'pointer' }}
            >
              Clear All
            </button>
          </div>

          <div className="selected-files-list">
            {selectedFiles.map((file, idx) => (
              <span key={idx} className="file-chip">
                <span>{file.name}</span>
                <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>({(file.size / 1024).toFixed(0)} KB)</span>
                <button type="button" className="remove-btn" onClick={() => removeFile(idx)}>
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>

          <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Auditing with Azure Document Intelligence...
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Process Batch ({selectedFiles.length} files)
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Status Alert Banner */}
      {uploadStatus && (
        <div
          style={{
            marginTop: '16px',
            padding: '12px 16px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: uploadStatus.type === 'success' ? '#ecfdf5' : '#fff1f2',
            color: uploadStatus.type === 'success' ? '#047857' : '#be123c',
            border: `1px solid ${uploadStatus.type === 'success' ? '#a7f3d0' : '#fecdd3'}`,
          }}
        >
          {uploadStatus.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{uploadStatus.message}</span>
        </div>
      )}
    </div>
  );
}


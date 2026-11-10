import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function SettingsScreen({ academicTerm = 'Fall 2026', onAcademicTermChange }) {
  const { user, updateProfile } = useAuth();
  const [selectedTerm, setSelectedTerm] = useState(user?.term_preference || academicTerm || 'Fall 2026');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const termDefinitions = {
    'Fall 2026': { start: '2026-08-01', end: '2026-12-31', desc: 'Autumn Semester 2026' },
    'Spring 2027': { start: '2027-01-01', end: '2027-05-31', desc: 'Spring Semester 2027' },
    'Summer 2026': { start: '2026-06-01', end: '2026-07-31', desc: 'Summer Term 2026' },
    'AY 2026-27': { start: '2026-06-01', end: '2027-05-31', desc: 'Full Consolidated Academic Year' },
  };

  const handleSaveTerm = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      if (onAcademicTermChange) onAcademicTermChange(selectedTerm);
      if (updateProfile) await updateProfile(user?.full_name, selectedTerm);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const activeTermInfo = termDefinitions[selectedTerm] || termDefinitions['Fall 2026'];

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Audit Preferences &amp; Settings</h1>
        <p className="text-xs text-slate-500 mt-1">
          Configure active academic terms, deterministic validation thresholds, and extraction models.
        </p>
      </div>

      {saveSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px] text-emerald-600">check_circle</span>
          <span>Preferences updated successfully and persisted to profile.</span>
        </div>
      )}

      {/* Card 1: Academic Term & Calendar */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
          <span className="material-symbols-outlined text-blue-600 text-[20px]">calendar_month</span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Academic Term Boundaries (Rule V04)</h2>
            <p className="text-xs text-slate-500">
              Documents dated outside this window are automatically flagged with V04 Out-of-Term violations.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-700 font-semibold mb-1">Select Active Term:</label>
            <select
              value={selectedTerm}
              onChange={(e) => setSelectedTerm(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-800 font-medium focus:ring-1 focus:ring-blue-600 focus:outline-none"
            >
              <option value="Fall 2026">Fall 2026 (Aug 1 - Dec 31, 2026)</option>
              <option value="Spring 2027">Spring 2027 (Jan 1 - May 31, 2027)</option>
              <option value="Summer 2026">Summer 2026 (Jun 1 - Jul 31, 2026)</option>
              <option value="AY 2026-27">AY 2026-27 (Full Academic Year)</option>
            </select>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1 font-mono text-[11px]">
            <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Active Boundary Dates</div>
            <div>Start: <strong className="text-slate-800">{activeTermInfo.start}</strong></div>
            <div>End: <strong className="text-slate-800">{activeTermInfo.end}</strong></div>
            <div className="text-slate-400 text-[10px]">{activeTermInfo.desc}</div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleSaveTerm}
            disabled={isSaving}
            className="px-4 py-2 bg-[#0f172a] hover:bg-[#1e293b] text-white rounded-lg text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save Term Preferences'}
          </button>
        </div>
      </div>

      {/* Card 2: OCR & Deterministic Rules Specification */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
          <span className="material-symbols-outlined text-blue-600 text-[20px]">verified_user</span>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Deterministic Engine Parameters</h2>
            <p className="text-xs text-slate-500">
              Zero-LLM financial accounting rules according to institutional compliance standards.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase block mb-1">OCR Confidence Threshold</span>
            <span className="text-base font-mono font-bold text-slate-900">85.0% (0.85)</span>
            <p className="text-[11px] text-slate-500 mt-1">Rule V05 triggers a warning on any field extracted with confidence below 0.85.</p>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase block mb-1">Azure Engine Model</span>
            <span className="text-base font-mono font-bold text-slate-900">Dual Prebuilt</span>
            <p className="text-[11px] text-slate-500 mt-1">Auto-routes to <code>prebuilt-invoice</code> or <code>prebuilt-receipt</code> based on filename &amp; headers.</p>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase block mb-1">Arithmetic Precision</span>
            <span className="text-base font-mono font-bold text-slate-900">Decimal (Text)</span>
            <p className="text-[11px] text-slate-500 mt-1">Stored as canonical decimal strings to prevent IEEE-754 floating-point rounding errors.</p>
          </div>
        </div>
      </div>

      {/* Card 3: System Environment Details */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-3">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span className="material-symbols-outlined text-slate-500 text-[18px]">info</span>
          System Specifications
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 block uppercase">Azure API Version</span>
            <span className="font-semibold text-slate-800">2024-11-30</span>
          </div>
          <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 block uppercase">Currency</span>
            <span className="font-semibold text-slate-800">INR (₹)</span>
          </div>
          <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 block uppercase">Supported Formats</span>
            <span className="font-semibold text-slate-800">PDF, PNG, JPEG</span>
          </div>
          <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 block uppercase">Max Upload</span>
            <span className="font-semibold text-slate-800">20 MB / file</span>
          </div>
        </div>
      </div>
    </div>
  );
}


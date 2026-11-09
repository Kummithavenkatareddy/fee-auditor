import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ConfidenceBadge from '../components/ConfidenceBadge';
import StatusBadge from '../components/StatusBadge';
import SeverityBadge from '../components/SeverityBadge';
import SummaryCards from '../components/SummaryCards';
import DocumentsTable from '../components/DocumentsTable';

describe('ConfidenceBadge Component', () => {
  it('renders high confidence (>= 90%) with green indicator', () => {
    const { container } = render(<ConfidenceBadge confidence={0.96} status="extracted" />);
    expect(screen.getByText('96%')).toBeInTheDocument();
    expect(container.querySelector('.bg-\\[\\#EBF5F0\\]')).toBeInTheDocument();
  });

  it('renders acceptable confidence (85% to 89%) with blue indicator', () => {
    const { container } = render(<ConfidenceBadge confidence={0.87} status="extracted" />);
    expect(screen.getByText('87%')).toBeInTheDocument();
    expect(container.querySelector('.bg-\\[\\#EFF3F8\\]')).toBeInTheDocument();
  });

  it('renders low confidence (< 85%) with amber indicator and Low label', () => {
    const { container } = render(<ConfidenceBadge confidence={0.72} status="low_confidence" />);
    expect(screen.getByText(/72% Low/i)).toBeInTheDocument();
    expect(container.querySelector('.bg-\\[\\#FEF7EC\\]')).toBeInTheDocument();
  });

  it('renders Missing badge when value is missing', () => {
    render(<ConfidenceBadge status="missing" />);
    expect(screen.getByText(/missing/i)).toBeInTheDocument();
  });

  it('renders N/A for not applicable fields', () => {
    render(<ConfidenceBadge status="not_applicable" />);
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });
});

describe('StatusBadge Component', () => {
  it('renders clean status badge', () => {
    render(<StatusBadge status="clean" />);
    expect(screen.getByText(/Clean \/ Validated/i)).toBeInTheDocument();
  });

  it('renders flagged status with highest severity', () => {
    render(<StatusBadge status="flagged" highestSeverity="CRITICAL" />);
    expect(screen.getByText(/Flagged \(CRITICAL\)/i)).toBeInTheDocument();
  });

  it('renders auditor reviewed status badge', () => {
    render(<StatusBadge status="reviewed" />);
    expect(screen.getByText(/Auditor Reviewed/i)).toBeInTheDocument();
  });
});

describe('SeverityBadge Component', () => {
  it('renders CRITICAL severity in bold uppercase', () => {
    render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });

  it('renders HIGH severity', () => {
    render(<SeverityBadge severity="HIGH" />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders MEDIUM severity', () => {
    render(<SeverityBadge severity="MEDIUM" />);
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
  });

  it('renders WARNING severity', () => {
    render(<SeverityBadge severity="WARNING" />);
    expect(screen.getByText('WARNING')).toBeInTheDocument();
  });
});

describe('Currency and Metric Consistency', () => {
  it('renders SummaryCards with Indian Rupee (₹) symbol', () => {
    const summary = {
      total_documents: 6,
      clean_documents: 3,
      flagged_documents: 3,
      low_confidence_documents: 0,
      total_value: 9794.0,
    };
    render(<SummaryCards summary={summary} />);
    expect(screen.getByText(/₹9,794\.00/i)).toBeInTheDocument();
  });

  it('renders DocumentsTable total with Indian Rupee (₹) symbol', () => {
    const sampleDocs = [
      {
        id: 'doc-1',
        file_name: 'INV-001.pdf',
        document_type: 'invoice',
        vendor_name: { value: 'Aster Supplies', confidence: 0.98 },
        invoice_id: { value: 'INV-2026-001', confidence: 0.95 },
        invoice_date: { value: '2026-09-12', confidence: 0.96 },
        total: { value: '9794.00', confidence: 0.97 },
        validation_flags: [],
        audit_status: 'clean',
        manual_review_status: 'pending',
      },
    ];
    render(
      <DocumentsTable
        documents={sampleDocs}
        filter="all"
        onFilterChange={() => {}}
        onSelectDoc={() => {}}
      />
    );
    expect(screen.getByText(/₹9,794\.00/i)).toBeInTheDocument();
  });
});


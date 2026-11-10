import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DocumentWorkspace from '../components/DocumentWorkspace';
import AppShell from '../components/AppShell';
import { AuthProvider } from '../context/AuthContext';

// Mock API functions used in DocumentWorkspace
vi.mock('../services/api', () => ({
  updateManualReview: vi.fn().mockResolvedValue({ success: true }),
  revalidateDocument: vi.fn().mockResolvedValue({ success: true }),
  getDocumentFileUrl: vi.fn((id) => `http://localhost:8000/api/audit/documents/${id}/file`),
}));

const mockDoc = {
  id: 'doc-p08-test-12345678',
  file_name: 'INV-2026-001.pdf',
  document_type: 'invoice',
  model_used: 'prebuilt-invoice',
  audit_status: 'flagged',
  highest_severity: 'HIGH',
  manual_review_status: 'pending',
  manual_review_notes: '',
  vendor_name: { value: 'Apex Global Technologies', confidence: 0.88, status: 'extracted' },
  invoice_id: { value: 'INV-2026-001', confidence: 0.95, status: 'extracted' },
  invoice_date: { value: '2026-09-15', confidence: 0.92, status: 'extracted' },
  vendor_tax_id: { value: '27AABCA1234F1Z5', confidence: 0.90, status: 'extracted' },
  subtotal: { value: 10000.0, confidence: 0.94, status: 'extracted' },
  cgst: { value: 900.0, confidence: 0.91, status: 'extracted' },
  sgst: { value: 900.0, confidence: 0.91, status: 'extracted' },
  tax: { value: 1800.0, confidence: 0.93, status: 'extracted' },
  total: { value: 11800.0, confidence: 0.96, status: 'extracted' },
  line_items: [
    { description: 'Cloud Infrastructure Consulting', quantity: 1, unit_price: 6000.0, amount: 6000.0, confidence: 0.92 },
    { description: 'Database Audit & Migration', quantity: 1, unit_price: 4000.0, amount: 4000.0, confidence: 0.89 },
  ],
  validation_flags: [
    {
      rule_id: 'V01',
      rule_name: 'Arithmetic Verification',
      severity: 'HIGH',
      field_name: 'total',
      reason: 'Total does not match subtotal plus tax due to rounding variance.',
      expected_value: '11800.00',
      actual_value: '11800.00',
    },
  ],
  reconciliation: {
    status: 'RECONCILED',
    is_reconciled: true,
    calculation_type: 'tax_exclusive',
    line_items_sum: 10000.0,
    extracted_subtotal: 10000.0,
    cgst: 900.0,
    sgst: 900.0,
    igst: null,
    total_tax: 1800.0,
    expected_grand_total: 11800.0,
    extracted_grand_total: 11800.0,
    variance: 0.0,
    explanation: 'Subtotal ₹10,000.00 + CGST ₹900.00 + SGST ₹900.00 matches Grand Total ₹11,800.00.',
  },
  raw_azure_json: JSON.stringify({
    status: 'succeeded',
    documents: [{ docType: 'invoice', confidence: 0.94 }],
  }),
};

describe('P08 — Full-Width Document Workspace Layout & Non-Sticky Scrolling', () => {
  it('renders with 100% full width and no max-w-7xl centered constraints', () => {
    const { container } = render(
      <DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />
    );

    const workspaceRoot = container.firstChild;
    expect(workspaceRoot).toHaveClass('w-full');
    expect(workspaceRoot).not.toHaveClass('max-w-7xl');
    expect(workspaceRoot).not.toHaveClass('mx-auto');
  });

  it('renders document action toolbar in normal document flow (NOT sticky, NOT fixed)', () => {
    const { container } = render(
      <DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />
    );

    // Find the toolbar containing document filename and actions
    const toolbar = screen.getByText('INV-2026-001.pdf').closest('.border-b');
    expect(toolbar).toBeInTheDocument();

    // Verify non-sticky, non-fixed positioning: toolbar scrolls naturally with page
    expect(toolbar).not.toHaveClass('sticky');
    expect(toolbar).not.toHaveClass('fixed');
    expect(toolbar).not.toHaveClass('top-16');
    expect(toolbar).not.toHaveClass('z-30');
  });

  it('renders all mandatory toolbar controls in normal page flow', () => {
    const handleClose = vi.fn();
    render(<DocumentWorkspace doc={mockDoc} onClose={handleClose} onUpdated={vi.fn()} />);

    // Filename & Status Badge
    expect(screen.getByText('INV-2026-001.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Flagged/i)).toBeInTheDocument();

    // Action buttons
    expect(screen.getByRole('button', { name: /Revalidate/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Azure JSON/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Download Original/i })).toBeInTheDocument();

    // Close button
    const closeBtn = screen.getByTitle('Close Workspace');
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders desktop responsive grid split: ~42% PDF viewer (5 cols) and ~58% extraction panel (7 cols)', () => {
    const { container } = render(
      <DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />
    );

    // Main grid container
    const gridContainer = container.querySelector('.grid.grid-cols-1.lg\\:grid-cols-12');
    expect(gridContainer).toBeInTheDocument();

    // Left pane (PDF Viewer): lg:col-span-5
    const leftPane = container.querySelector('.lg\\:col-span-5');
    expect(leftPane).toBeInTheDocument();
    // Must NOT be sticky
    expect(leftPane).not.toHaveClass('sticky');
    expect(leftPane).not.toHaveClass('top-36');

    // Right pane (Extraction details): lg:col-span-7
    const rightPane = container.querySelector('.lg\\:col-span-7');
    expect(rightPane).toBeInTheDocument();
    expect(rightPane).toHaveClass('min-w-0');
  });

  it('renders PDF viewer controls including Rotate, Fit, and Zoom', () => {
    render(<DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />);

    expect(screen.getByTitle('Zoom Out')).toBeInTheDocument();
    expect(screen.getByTitle('Zoom In')).toBeInTheDocument();
    expect(screen.getByTitle('Fit Screen')).toBeInTheDocument();
    expect(screen.getByTitle('Rotate 90 degrees')).toBeInTheDocument();
    expect(screen.getByText('PDF Binary')).toBeInTheDocument();
    expect(screen.getByText('Auditor Canvas')).toBeInTheDocument();
  });

  it('switches between PDF Binary and Auditor Canvas view modes and rotates', () => {
    const { container } = render(
      <DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />
    );

    // Initial: PDF Binary iframe is present
    expect(container.querySelector('iframe')).toBeInTheDocument();

    // Rotate button click
    const rotateBtn = screen.getByTitle('Rotate 90 degrees');
    fireEvent.click(rotateBtn);

    // Switch to Auditor Canvas
    const canvasBtn = screen.getByText('Auditor Canvas');
    fireEvent.click(canvasBtn);
    expect(screen.getByText('ACCOUNTS VERIFIED')).toBeInTheDocument();

    // Reset zoom and rotation via Fit Screen
    const fitBtn = screen.getByTitle('Fit Screen');
    fireEvent.click(fitBtn);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('renders line items table in normal document flow without restrictive max-h-56 vertical scroll', () => {
    const { container } = render(
      <DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />
    );

    expect(screen.getByText(/Line Items Detail \(2\)/i)).toBeInTheDocument();

    // Line items wrapper should NOT have max-h-56
    const lineItemsWrapper = screen.getByText('Cloud Infrastructure Consulting').closest('.overflow-x-auto');
    expect(lineItemsWrapper).toBeInTheDocument();
    expect(lineItemsWrapper).not.toHaveClass('max-h-56');
    expect(lineItemsWrapper).not.toHaveClass('overflow-y-auto');
  });

  it('renders audit findings reasons with break-words to prevent layout breaking', () => {
    render(<DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />);

    const reasonEls = screen.getAllByText(/Total does not match subtotal plus tax due to rounding variance/i);
    const pReason = reasonEls.find((el) => el.tagName === 'P');
    expect(pReason).toHaveClass('break-words');
  });

  it('opens and closes Azure JSON raw extraction modal', () => {
    render(<DocumentWorkspace doc={mockDoc} onClose={vi.fn()} onUpdated={vi.fn()} />);

    // Click Azure JSON
    fireEvent.click(screen.getByRole('button', { name: /Azure JSON/i }));
    expect(screen.getByText(/Azure AI Document Intelligence: Raw Extraction Payload/i)).toBeInTheDocument();

    // Close modal (find close button inside modal)
    const closeIcons = screen.getAllByText('close');
    const modalCloseIcon = closeIcons[closeIcons.length - 1];
    fireEvent.click(modalCloseIcon);
    expect(screen.queryByText(/Azure AI Document Intelligence: Raw Extraction Payload/i)).not.toBeInTheDocument();
  });
});

describe('AppShell Full-Width Document Workspace Integration', () => {
  it('removes max-w-7xl and padding constraints from main content area when selectedDoc is present', () => {
    const { container } = render(
      <AuthProvider>
        <AppShell activeTab="documents" selectedDoc={mockDoc}>
          <div data-testid="workspace-content">Workspace Content</div>
        </AppShell>
      </AuthProvider>
    );

    const mainEl = container.querySelector('main');
    expect(mainEl).toHaveClass('p-0');
    expect(mainEl).not.toHaveClass('px-6');

    const innerDiv = screen.getByTestId('workspace-content').parentElement;
    expect(innerDiv).toHaveClass('w-full');
    expect(innerDiv).not.toHaveClass('max-w-7xl');
    expect(innerDiv).not.toHaveClass('mx-auto');
  });

  it('preserves standard max-w-7xl layout and padding when no document is selected', () => {
    const { container } = render(
      <AuthProvider>
        <AppShell activeTab="documents" selectedDoc={null}>
          <div data-testid="library-content">Library Content</div>
        </AppShell>
      </AuthProvider>
    );

    const mainEl = container.querySelector('main');
    expect(mainEl).toHaveClass('px-6');
    expect(mainEl).toHaveClass('py-5');

    const innerDiv = screen.getByTestId('library-content').parentElement;
    expect(innerDiv).toHaveClass('max-w-7xl');
    expect(innerDiv).toHaveClass('mx-auto');
  });

  it('includes smooth width transition for desktop sidebar collapse/expansion', () => {
    const { container } = render(
      <AuthProvider>
        <AppShell activeTab="dashboard" selectedDoc={null}>
          <div>Dashboard</div>
        </AppShell>
      </AuthProvider>
    );

    // Sidebar wrapper should have transition-[width,transform]
    const sidebarWrapper = container.querySelector('.transition-\\[width\\,transform\\]');
    expect(sidebarWrapper).toBeInTheDocument();
  });
});

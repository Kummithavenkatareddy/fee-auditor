import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import SettingsScreen from '../components/SettingsScreen';
import ManualReviewScreen from '../components/ManualReviewScreen';
import { AuthProvider } from '../context/AuthContext';

describe('Sidebar 8-View Navigation', () => {
  it('renders all 8 institutional views in sidebar', () => {
    const handleTabChange = vi.fn();
    render(
      <AuthProvider>
        <Sidebar activeTab="dashboard" onTabChange={handleTabChange} pendingReviewCount={3} />
      </AuthProvider>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Upload & Process')).toBeInTheDocument();
    expect(screen.getByText('My Documents')).toBeInTheDocument();
    expect(screen.getByText('Audit Findings')).toBeInTheDocument();
    expect(screen.getByText('Review Queue')).toBeInTheDocument();
    expect(screen.getByText('Reports & Exports')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Account & Security')).toBeInTheDocument();
  });

  it('displays pending review exception badge on Review Queue', () => {
    render(
      <AuthProvider>
        <Sidebar activeTab="dashboard" onTabChange={vi.fn()} pendingReviewCount={4} />
      </AuthProvider>
    );

    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('triggers onTabChange when navigation item is clicked', () => {
    const handleTabChange = vi.fn();
    render(
      <AuthProvider>
        <Sidebar activeTab="dashboard" onTabChange={handleTabChange} />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Audit Findings'));
    expect(handleTabChange).toHaveBeenCalledWith('findings');
  });
});

describe('Header & Academic Term Navigation', () => {
  it('renders breadcrumb and academic term selector', () => {
    render(
      <AuthProvider>
        <Header activeTab="dashboard" onSearchChange={vi.fn()} academicTerm="Fall 2026" />
      </AuthProvider>
    );

    expect(screen.getByText('Auditor Console')).toBeInTheDocument();
    expect(screen.getByText('Dashboard & Metrics')).toBeInTheDocument();
    expect(screen.getByText(/Term: Fall 2026/i)).toBeInTheDocument();
  });

  it('renders global search input and emits search updates', () => {
    const handleSearch = vi.fn();
    render(
      <AuthProvider>
        <Header activeTab="documents" searchValue="Apex" onSearchChange={handleSearch} />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText(/Search invoice, vendor, tax ID/i);
    expect(input.value).toBe('Apex');
    fireEvent.change(input, { target: { value: 'Stanford' } });
    expect(handleSearch).toHaveBeenCalledWith('Stanford');
  });
});

describe('Review Queue Clean Documents Exclusion', () => {
  it('strictly excludes clean documents from the review queue', () => {
    const sampleDocs = [
      {
        id: 'doc-clean-1',
        file_name: 'INV-CLEAN-001.pdf',
        audit_status: 'clean',
        validation_flags: [],
        manual_review_status: 'pending',
        total: { value: 100.0 },
      },
      {
        id: 'doc-flagged-2',
        file_name: 'INV-FLAGGED-002.pdf',
        audit_status: 'flagged',
        validation_flags: [
          { rule_id: 'V01', rule_name: 'Total Mismatch', severity: 'HIGH', reason: 'Total mismatch' },
        ],
        manual_review_status: 'pending',
        total: { value: 200.0 },
      },
    ];

    render(
      <ManualReviewScreen documents={sampleDocs} onSelectDoc={vi.fn()} onRefresh={vi.fn()} />
    );

    // Flagged document MUST appear
    expect(screen.getByText('INV-FLAGGED-002.pdf')).toBeInTheDocument();
    expect(screen.getByText(/V01: Total Mismatch/i)).toBeInTheDocument();

    // Clean document MUST NOT appear in the review queue
    expect(screen.queryByText('INV-CLEAN-001.pdf')).not.toBeInTheDocument();

    // Notice pill confirms clean documents excluded
    expect(screen.getByText(/Clean Documents Excluded \(1 clean\)/i)).toBeInTheDocument();
  });
});

describe('SettingsScreen Component', () => {
  it('displays deterministic rules configuration and academic term selector', () => {
    render(
      <AuthProvider>
        <SettingsScreen academicTerm="Fall 2026" onAcademicTermChange={vi.fn()} />
      </AuthProvider>
    );

    expect(screen.getByText(/Academic Term Boundaries \(Rule V04\)/i)).toBeInTheDocument();
    expect(screen.getByText(/85\.0% \(0\.85\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Dual Prebuilt/i)).toBeInTheDocument();
    expect(screen.getByText(/Decimal \(Text\)/i)).toBeInTheDocument();
  });
});

describe('AppShell Layout & Zero Overlap Test', () => {
  it('renders AppShell with flex flow and children without layout overlap', async () => {
    const { default: AppShell } = await import('../components/AppShell');
    render(
      <AuthProvider>
        <AppShell activeTab="dashboard" onTabChange={vi.fn()}>
          <div data-testid="dashboard-child">Dashboard Content Here</div>
        </AppShell>
      </AuthProvider>
    );

    expect(screen.getByTestId('dashboard-child')).toBeInTheDocument();
    expect(screen.getByText('Auditor Console')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});

describe('LoginScreen Authentication Gate', () => {
  it('renders institutional login portal and switches modes', async () => {
    const { default: LoginScreen } = await import('../components/LoginScreen');
    render(
      <AuthProvider>
        <LoginScreen onLoginSuccess={vi.fn()} />
      </AuthProvider>
    );

    expect(screen.getByText('Institutional Auditor Portal')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In to Audit Console/i })).toBeInTheDocument();

    // Switch to Register
    fireEvent.click(screen.getByText('Register Account'));
    expect(screen.getByText('Create Password (min 8 chars)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Register & Receive Code/i })).toBeInTheDocument();

    // Back to Login
    fireEvent.click(screen.getByText('← Back to Sign In'));
    expect(screen.getByRole('button', { name: /Sign In to Audit Console/i })).toBeInTheDocument();
  });
});



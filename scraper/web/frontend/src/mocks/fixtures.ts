import type { Bill, BillsResponse, ScrapeJob } from '../types';

export const mockJurisdictions: string[] = [
  'congress.gov',
  'federalregister.gov',
  'leginfo.legislature.ca.gov',
  'le.utah.gov',
];

export const mockBills: Bill[] = [
  {
    id: 1001,
    source_url: 'https://www.congress.gov/bill/118th-congress/house-bill/1234',
    search_term: '"AI Bill" site:congress.gov inurl:/bill',
    domain: 'congress.gov',
    created_at: '2026-05-19T10:30:00Z',
    excerpt:
      'A bill to establish transparency requirements for automated decision systems used by federal agencies...',
    text_processing_method: 'Congress.gov API (HTM)',
  },
  {
    id: 1002,
    source_url: 'https://www.congress.gov/bill/118th-congress/senate-bill/5678',
    search_term: '"Algorithmic accountability" site:congress.gov inurl:/bill',
    domain: 'congress.gov',
    created_at: '2026-05-19T10:28:00Z',
    excerpt:
      'A bill to require algorithmic impact assessments before deployment of high-risk AI systems...',
    text_processing_method: 'Congress.gov API (HTM)',
  },
  {
    id: 1003,
    source_url: 'https://www.federalregister.gov/documents/2026/01/15/2026-00123/example-ai-rulemaking',
    search_term: '"AI rulemaking" site:federalregister.gov',
    domain: 'federalregister.gov',
    created_at: '2026-05-19T10:21:00Z',
    excerpt:
      'The agency requests public comment on proposed guidance for use of AI in administrative adjudication...',
    text_processing_method: 'Federal Register API',
  },
];

export const mockBillsResponse: BillsResponse = {
  bills: mockBills,
  total: mockBills.length,
  page: 1,
  per_page: 20,
  total_pages: 1,
};

export const mockBillById: Record<number, Bill> = Object.fromEntries(
  mockBills.map((bill) => [bill.id, bill]),
);

export const mockJobRunning: ScrapeJob = {
  job_id: 'mock-job-running',
  status: 'running',
  runtime_seconds: 98,
  log_size_bytes: 3221,
  last_log_update_seconds_ago: 4,
  activity_state: 'active',
  config: {
    terms: ['AI Bill', 'Algorithmic accountability'],
    jurisdictions: {
      'congress.gov': { signals: ['/bill'] },
      'federalregister.gov': {},
    },
    start_date: '2026-01-01',
    end_date: '2026-05-01',
  },
};

export const mockJobCompleted: ScrapeJob = {
  job_id: 'mock-job-completed',
  status: 'completed',
  config: {
    terms: ['AI Bill', 'Algorithmic accountability'],
    jurisdictions: {
      'congress.gov': { signals: ['/bill'] },
      'federalregister.gov': {},
    },
    start_date: '2026-01-01',
    end_date: '2026-05-01',
  },
  results: {
    total_URLs: 7,
    successful_URLs: 5,
    failed_URLs: 2,
    processed_urls: [
      {
        url: 'https://www.congress.gov/bill/118th-congress/house-bill/1234',
        success: true,
      },
      {
        url: 'https://www.congress.gov/bill/118th-congress/senate-bill/5678',
        success: true,
      },
      {
        url: 'https://www.federalregister.gov/documents/2026/01/15/2026-00123/example-ai-rulemaking',
        success: true,
      },
      {
        url: 'https://www.congress.gov/bill/118th-congress/house-bill/9012',
        success: false,
        error: 'Failed to retrieve HTML after retries',
      },
    ],
    scheduled: {
      new_urls_found: 3,
      urls_fixed: 2,
    },
  },
};

export const mockJobFailed: ScrapeJob = {
  job_id: 'mock-job-failed',
  status: 'failed',
  config: {
    terms: ['AI Bill'],
    jurisdictions: {
      'congress.gov': { signals: ['/bill'] },
    },
  },
  log: 'FATAL ERROR: Mocked backend failure while processing batch 3',
};

export const mockScrapeJobs: ScrapeJob[] = [
  mockJobRunning,
  mockJobCompleted,
  mockJobFailed,
];

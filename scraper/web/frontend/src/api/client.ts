import type { Bill, BillsResponse, ScrapeConfig, ScrapeJob } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL?.trim() || '/api';

export async function fetchJurisdictions(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/jurisdictions`);
  if (!res.ok) throw new Error('Failed to fetch jurisdictions');
  return res.json();
}

export async function fetchBills(params: {
  jurisdiction?: string;
  page?: number;
  per_page?: number;
}): Promise<BillsResponse> {
  const searchParams = new URLSearchParams();
  if (params.jurisdiction) searchParams.set('jurisdiction', params.jurisdiction);
  if (params.page) searchParams.set('page', params.page.toString());
  if (params.per_page) searchParams.set('per_page', params.per_page.toString());
  
  const res = await fetch(`${API_BASE}/bills?${searchParams}`);
  if (!res.ok) throw new Error('Failed to fetch bills');
  return res.json();
}

export async function fetchBill(id: number): Promise<Bill> {
  const res = await fetch(`${API_BASE}/bills/${id}`);
  if (!res.ok) throw new Error('Failed to fetch bill');
  return res.json();
}

export async function createScrape(config: ScrapeConfig): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/scrapes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.error || 'Failed to create scrape');
  }
  return res.json();
}

export async function fetchScrapeJob(jobId: string): Promise<ScrapeJob> {
  const res = await fetch(`${API_BASE}/scrapes/${jobId}`);
  if (!res.ok) throw new Error('Failed to fetch scrape job');
  return res.json();
}

export async function fetchScrapeJobs(): Promise<ScrapeJob[]> {
  const res = await fetch(`${API_BASE}/scrapes`);
  if (!res.ok) throw new Error('Failed to fetch scrape jobs');
  return res.json();
}

export const PRESET_JURISDICTIONS: Record<string, { signals?: string[] }> = {
  'congress.gov': { signals: ['/bill'] },
  'federalregister.gov': {},
  'leginfo.legislature.ca.gov': { signals: ['/bill'] },
  'eur-lex.europa.eu': {},
  'legislation.gov.uk': {},
  'parl.ca/legisinfo': {},
  'capitol.texas.gov': {},
  'leg.colorado.gov': { signals: ['/bills'] },
  'le.utah.gov': { signals: ['/bills'] },
  'nyassembly.gov': { signals: ['/leg'] },
  'nist.gov': { signals: ['/nistpubs'] },
  'whitehouse.gov': {},
  'lis.virginia.gov': {},
  'ilga.gov': { signals: ['/legislation'] },
};

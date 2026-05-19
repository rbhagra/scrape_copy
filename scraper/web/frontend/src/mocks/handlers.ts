import { http, HttpResponse, delay } from 'msw';
import {
  mockBillById,
  mockBillsResponse,
  mockJobCompleted,
  mockJobFailed,
  mockJobRunning,
  mockJurisdictions,
  mockScrapeJobs,
} from './fixtures';

const API_BASE = '/api';

export const handlers = [
  http.get(`${API_BASE}/jurisdictions`, async () => {
    await delay(250);
    return HttpResponse.json(mockJurisdictions);
  }),

  http.get(`${API_BASE}/bills`, async ({ request }) => {
    await delay(350);
    const url = new URL(request.url);
    const page = Number(url.searchParams.get('page') || '1');
    const perPage = Number(url.searchParams.get('per_page') || '20');

    return HttpResponse.json({
      ...mockBillsResponse,
      page,
      per_page: perPage,
    });
  }),

  http.get(`${API_BASE}/bills/:id`, async ({ params }) => {
    await delay(220);
    const id = Number(params.id);
    const bill = mockBillById[id];
    if (!bill) {
      return HttpResponse.json({ error: 'Bill not found (mock)' }, { status: 404 });
    }
    return HttpResponse.json(bill);
  }),

  http.post(`${API_BASE}/scrapes`, async () => {
    await delay(300);
    // Return running job id so UI navigates to /scrape/:jobId.
    return HttpResponse.json({
      job_id: mockJobRunning.job_id,
      status: 'running',
    });
  }),

  http.get(`${API_BASE}/scrapes/:jobId`, async ({ params }) => {
    await delay(300);
    const jobId = String(params.jobId || '');

    if (jobId === mockJobCompleted.job_id) {
      return HttpResponse.json(mockJobCompleted);
    }
    if (jobId === mockJobFailed.job_id) {
      return HttpResponse.json(mockJobFailed);
    }

    // Default mock behavior for newly created jobs.
    return HttpResponse.json({
      ...mockJobRunning,
      job_id: jobId || mockJobRunning.job_id,
    });
  }),

  http.get(`${API_BASE}/scrapes`, async () => {
    await delay(250);
    return HttpResponse.json(mockScrapeJobs);
  }),
];

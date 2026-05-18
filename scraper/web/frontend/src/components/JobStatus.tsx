import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchScrapeJob } from '../api/client';
import type { ScrapeJob } from '../types';

export default function JobStatus() {
  const { jobId } = useParams<{ jobId: string }>();

  const { data: job, isLoading, error } = useQuery<ScrapeJob>({
    queryKey: ['scrape', jobId],
    queryFn: () => fetchScrapeJob(jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 3000 : false;
    },
    enabled: !!jobId,
  });

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-md p-6">
          <h2 className="text-lg font-medium text-red-800 mb-2">Error</h2>
          <p className="text-red-700">Failed to load job status</p>
          <Link to="/scrape" className="text-blue-600 hover:text-blue-800 mt-4 inline-block">
            Start a new scrape
          </Link>
        </div>
      </div>
    );
  }

  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  const config = job.config as
    | {
        terms?: string[];
        jurisdictions?: Record<string, { signals?: string[] }>;
        start_date?: string;
        end_date?: string;
        Terms?: string[];
        'Jurisdictions and signal'?: Record<string, { signals?: string[] }>;
        Settings?: { 'Start Date'?: string; 'End Date'?: string };
      }
    | undefined;

  const searchTerms = config?.terms ?? config?.Terms ?? [];
  const jurisdictions =
    config?.jurisdictions ?? config?.['Jurisdictions and signal'] ?? {};
  const startDate = config?.start_date ?? config?.Settings?.['Start Date'];
  const endDate = config?.end_date ?? config?.Settings?.['End Date'];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Scrape Job</h2>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[job.status] || 'bg-gray-100 text-gray-800'}`}>
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-sm font-medium text-gray-900">Job ID</h3>
          <p className="text-sm text-gray-500 font-mono">{job.job_id}</p>
        </div>

        {config && (
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-sm font-medium text-gray-900 mb-2">Configuration</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-gray-500">Search Terms</dt>
                <dd className="text-gray-900">
                  {searchTerms.join(', ') || 'N/A'}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Jurisdictions</dt>
                <dd className="text-gray-900">
                  {Object.keys(jurisdictions).join(', ') || 'N/A'}
                </dd>
              </div>
              {startDate && (
                <div>
                  <dt className="text-gray-500">Start Date</dt>
                  <dd className="text-gray-900">{startDate}</dd>
                </div>
              )}
              {endDate && (
                <div>
                  <dt className="text-gray-500">End Date</dt>
                  <dd className="text-gray-900">{endDate}</dd>
                </div>
              )}
            </dl>
          </div>
        )}

        {job.status === 'running' && (
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center">
              <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm text-gray-600">Scraping in progress... This page will update automatically.</span>
            </div>
            <div className="mt-3 text-sm text-gray-600 space-y-1">
              <p>
                Activity:{' '}
                <span className={job.activity_state === 'stalled' ? 'text-amber-700 font-medium' : 'text-green-700 font-medium'}>
                  {job.activity_state === 'stalled' ? 'Stalled' : 'Active'}
                </span>
              </p>
              {typeof job.runtime_seconds === 'number' && (
                <p>Runtime: {Math.floor(job.runtime_seconds / 60)}m {job.runtime_seconds % 60}s</p>
              )}
              {typeof job.log_size_bytes === 'number' && (
                <p>Log size: {job.log_size_bytes.toLocaleString()} bytes</p>
              )}
              {typeof job.last_log_update_seconds_ago === 'number' && (
                <p>Last log update: {job.last_log_update_seconds_ago}s ago</p>
              )}
              {job.activity_note && (
                <p className="text-amber-700">{job.activity_note}</p>
              )}
            </div>
          </div>
        )}

        {job.status === 'completed' && job.results && (
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Results Summary</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm mb-4">
              <div>
                <dt className="text-gray-500">Total URLs</dt>
                <dd className="text-2xl font-semibold text-gray-900">
                  {job.results.total_URLs ?? 0}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Successful</dt>
                <dd className="text-2xl font-semibold text-green-600">
                  {job.results.successful_URLs ?? 0}
                </dd>
              </div>
            </dl>
            
            {job.results.processed_urls && job.results.processed_urls.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Scraped Bills</h4>
                <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-md">
                  <ul className="divide-y divide-gray-200">
                    {job.results.processed_urls
                      .filter((item: { url: string; success: boolean }) => item.success)
                      .map((item: { url: string; success: boolean }, idx: number) => (
                        <li key={idx} className="px-3 py-2 hover:bg-gray-50">
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:text-blue-800 hover:underline break-all"
                          >
                            {item.url}
                          </a>
                        </li>
                      ))}
                  </ul>
                </div>
                {(job.results.failed_URLs ?? 0) > 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    {job.results.failed_URLs ?? 0} URL(s) failed to process
                  </p>
                )}
              </div>
            )}
            
            <div className="mt-4">
              <Link
                to="/"
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700"
              >
                Browse Bills
              </Link>
            </div>
          </div>
        )}

        {job.status === 'failed' && job.log && (
          <div className="px-6 py-4">
            <h3 className="text-sm font-medium text-gray-900 mb-2">Error Log</h3>
            <pre className="text-xs text-red-700 bg-red-50 p-4 rounded-md overflow-x-auto max-h-64">
              {job.log}
            </pre>
          </div>
        )}
      </div>

      <div className="flex justify-between">
        <Link
          to="/scrape"
          className="text-blue-600 hover:text-blue-800"
        >
          Start another scrape
        </Link>
        <Link
          to="/"
          className="text-gray-600 hover:text-gray-800"
        >
          Browse all bills
        </Link>
      </div>
    </div>
  );
}

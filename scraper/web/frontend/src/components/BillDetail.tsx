import { useQuery } from '@tanstack/react-query';
import { fetchBill } from '../api/client';

interface Props {
  billId: number;
  onClose: () => void;
}

function formatSearchTerm(searchTerm: string): string {
  const parts = searchTerm.match(/"[^"]+"|site:\S+|inurl:\S+/g);
  if (parts) {
    return parts.join(', ');
  } else {
    return searchTerm;
  }
}

export default function BillDetail({ billId, onClose }: Props) {
  const { data: bill, isLoading, error } = useQuery({
    queryKey: ['bill', billId],
    queryFn: () => fetchBill(billId),
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-lg shadow-blue-200 p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-6"></div>
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (error || !bill) {
    return (
      <div className="bg-white rounded-lg shadow-lg shadow-blue-200 p-6">
        <div className="text-red-600">Failed to load bill details</div>
        <button
          onClick={onClose}
          className="mt-4 text-sm text-blue-600 hover:text-blue-800"
        >
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg shadow-blue-200 overflow-hidden sticky top-20">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Bill Details</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Source URL</dt>
            <dd className="mt-1 italic">
              <a
                href={bill.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 break-all"
              >
                {bill.source_url}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Jurisdiction</dt>
            <dd className="mt-1 text-gray-900">{bill.domain}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Search Term</dt>
            <dd className="mt-1 text-gray-900">{formatSearchTerm(bill.search_term)}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Scraped At</dt>
            <dd className="mt-1 text-gray-900">
              {new Date(bill.created_at).toLocaleString()} EST
            </dd>
          </div>
          {bill.text_processing_method && (
            <div>
              <dt className="text-gray-500">Processing Method</dt>
              <dd className="mt-1 text-gray-900">{bill.text_processing_method}</dd>
            </div>
          )}
        </dl>
      </div>
      
      <div className="px-6 py-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">Full Text</h3>
        <div className="max-h-[600px] overflow-y-auto">
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
            {bill.clean_text || 'No text available'}
          </pre>
        </div>
      </div>
    </div>
  );
}

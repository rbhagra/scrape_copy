import { useQuery } from '@tanstack/react-query';
import { fetchBills } from '../api/client';
import type { Bill } from '../types';

interface Props {
  jurisdiction: string;
  page: number;
  onPageChange: (page: number) => void;
  onBillSelect: (bill: Bill) => void;
  selectedBillId?: number;
  sortBy?: 'ASC' | 'DESC';
}

// function to format bill url into something more readable
function formatUrl(url: string): string {
  try {
    const { hostname, pathname } = new URL(url);
    const parts = pathname.split('/').filter(Boolean);
    // parts: ['bill', '118th congress', 'house bill', '1234']
    // only works for urls like https://www.congress.gov/bill/118th-congress/house-bill/1234
    const congress = parts[1]; // 118th congress
    const type = parts[2];     // house bill
    const number = parts[3];   // 1234
    
    if (congress && type && number) {
      // returns hostname - type | number | congress
      return `${hostname} - ${type.replace(/-/g, ' ')} | ${number} | ${congress.replace(/-/g, ' ')}`;
    }
    return `${hostname} - ${parts[parts.length - 1]}`;
  } catch {
    return url;
  }
}

export default function BillsList({ jurisdiction, page, onPageChange, onBillSelect, selectedBillId, sortBy }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['bills', jurisdiction, page, sortBy],
    queryFn: () => fetchBills({ jurisdiction: jurisdiction || undefined, page, per_page: 20, sort: sortBy }),
  });

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-200 rounded"></div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-red-800">Failed to load bills. Please try again.</p>
      </div>
    );
  }

  if (!data?.bills.length) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-md p-8 text-center">
        <p className="text-gray-600">No bills found for this jurisdiction.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-500">
        Showing {(page - 1) * 20 + 1} - {Math.min(page * 20, data.total)} of {data.total} bills
      </div>
      
      <div className="space-y-2">
        {data.bills.map((bill) => (
          <div
            key={bill.id}
            onClick={() => onBillSelect(bill)}
            className={`p-4 rounded-lg border cursor-pointer transition-colors ${
              selectedBillId === bill.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {formatUrl(bill.source_url)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {bill.domain} | {bill.search_term} | {new Date(bill.created_at).toLocaleDateString()}
                </p>
                {bill.excerpt && (
                  <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                    {bill.excerpt}...
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {data.total_pages > 1 && (
        <div className="flex items-center justify-between pt-4">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">
            Page {page} of {data.total_pages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= data.total_pages}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

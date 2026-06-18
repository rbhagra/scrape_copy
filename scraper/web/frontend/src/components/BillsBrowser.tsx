import { useState } from 'react';
import JurisdictionSelector from './JurisdictionSelector';
import BillsList from './BillsList';
import BillDetail from './BillDetail';
import type { Bill } from '../types';

export default function BillsBrowser() {
  const [jurisdiction, setJurisdiction] = useState('');
  const [page, setPage] = useState(1);
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [sortBy, setSortBy] = useState<'ASC' | 'DESC'>('DESC');

  const handleJurisdictionChange = (newJurisdiction: string) => {
    setJurisdiction(newJurisdiction);
    setPage(1);
    setSelectedBill(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-blue-900">Browse Bills</h2>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <label htmlFor="sortBy" className="text-sm text-gray-500">
              Sort by:
            </label>
            <select
              id="sortBy"
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as 'ASC' | 'DESC');
                setPage(1);
              }}
              className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            >
              <option value="DESC">Newest First</option>
              <option value="ASC">Oldest First</option> 
            </select>
          </div>

          <div className="w-64">
            <JurisdictionSelector
              value={jurisdiction}
              onChange={handleJurisdictionChange}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <BillsList
            jurisdiction={jurisdiction}
            page={page}
            onPageChange={setPage}
            onBillSelect={setSelectedBill}
            selectedBillId={selectedBill?.id}
            sortBy={sortBy}
          />
        </div>
        
        <div className="lg:sticky lg:top-6">
          {selectedBill ? (
            <BillDetail
              billId={selectedBill.id}
              onClose={() => setSelectedBill(null)}
            />
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
              <p className="text-gray-500">Select a bill to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

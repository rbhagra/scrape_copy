import { useState } from 'react';
import JurisdictionSelector from './JurisdictionSelector';
import BillsList from './BillsList';
import BillDetail from './BillDetail';
import type { Bill } from '../types';

export default function BillsBrowser() {
  const [jurisdiction, setJurisdiction] = useState('');
  const [page, setPage] = useState(1);
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);

  const handleJurisdictionChange = (newJurisdiction: string) => {
    setJurisdiction(newJurisdiction);
    setPage(1);
    setSelectedBill(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Browse Bills</h2>
        <div className="w-64">
          <JurisdictionSelector
            value={jurisdiction}
            onChange={handleJurisdictionChange}
          />
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
          />
        </div>
        
        <div className="lg:sticky lg:top-6">
          {selectedBill ? (
            <BillDetail
              billId={selectedBill.id}
              onClose={() => setSelectedBill(null)}
            />
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
              <p className="text-gray-500">Select a bill to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

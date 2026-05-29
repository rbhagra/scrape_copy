import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { createScrape, PRESET_JURISDICTIONS } from '../api/client';

export default function ScrapeForm() {
  const navigate = useNavigate();
  const [terms, setTerms] = useState('');
  const [selectedJurisdictions, setSelectedJurisdictions] = useState<Set<string>>(new Set());
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const mutation = useMutation({
    mutationFn: createScrape,
    onSuccess: (data) => {
      navigate(`/scrape/${data.job_id}`);
    },
  });

  const toggleJurisdiction = (domain: string) => {
    const newSelected = new Set(selectedJurisdictions);
    if (newSelected.has(domain)) {
      newSelected.delete(domain);
    } else {
      newSelected.add(domain);
    }
    setSelectedJurisdictions(newSelected);
  };

  const selectAll = () => {
    setSelectedJurisdictions(new Set(Object.keys(PRESET_JURISDICTIONS)));
  };

  const clearAll = () => {
    setSelectedJurisdictions(new Set());
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const termsList = terms
      .split('\n')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    if (termsList.length === 0) {
      alert('Please enter at least one search term');
      return;
    }

    if (selectedJurisdictions.size === 0) {
      alert('Please select at least one jurisdiction');
      return;
    }

    const jurisdictions: Record<string, { signals?: string[] }> = {};
    for (const domain of selectedJurisdictions) {
      jurisdictions[domain] = PRESET_JURISDICTIONS[domain] || {};
    }

    mutation.mutate({
      terms: termsList,
      jurisdictions,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    });
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-blue-900 mb-6">New Scrape</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="terms" className="block text-sm font-bold text-gray-700 mb-1">
            Search Terms
          </label>
          <p className="text-sm text-gray-500 mb-2">
            Enter one search term per line
          </p>
          <textarea
            id="terms"
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            rows={6}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            placeholder="Artificial Intelligence&#10;AI Bills&#10;Algorithm"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-bold text-gray-700">
              Jurisdictions
            </label>
            <div className="space-x-2">
              <button
                type="button"
                onClick={selectAll}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Select All
              </button>
              <button
                type="button"
                onClick={clearAll}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 p-4 bg-gray-50 rounded-lg border border-gray-200 max-h-64 overflow-y-auto">
            {Object.entries(PRESET_JURISDICTIONS).map(([domain, config]) => (
              <label
                key={domain}
                className="flex items-start space-x-2 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedJurisdictions.has(domain)}
                  onChange={() => toggleJurisdiction(domain)}
                  className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm">
                  <span className="text-gray-900">{domain}</span>
                  {config.signals && config.signals.length > 0 && (
                    <span className="text-gray-500 text-xs block">
                      {config.signals.join(', ')}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {selectedJurisdictions.size} selected
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="startDate" className="block text-sm font-medium text-gray-700 mb-1">
              Start Date (optional)
            </label>
            <input
              type="date"
              id="startDate"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
          </div>
          <div>
            <label htmlFor="endDate" className="block text-sm font-medium text-gray-700 mb-1">
              End Date (optional)
            </label>
            <input
              type="date"
              id="endDate"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
          </div>
        </div>

        {mutation.error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">
              {mutation.error instanceof Error ? mutation.error.message : 'Failed to create scrape'}
            </p>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? 'Starting...' : 'Start Scrape'}
          </button>
        </div>
      </form>
    </div>
  );
}

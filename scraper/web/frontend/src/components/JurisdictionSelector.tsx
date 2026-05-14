import { useQuery } from '@tanstack/react-query';
import { fetchJurisdictions } from '../api/client';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function JurisdictionSelector({ value, onChange }: Props) {
  const { data: jurisdictions, isLoading, error } = useQuery({
    queryKey: ['jurisdictions'],
    queryFn: fetchJurisdictions,
  });

  if (isLoading) {
    return (
      <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm" disabled>
        <option>Loading jurisdictions...</option>
      </select>
    );
  }

  if (error) {
    return (
      <div className="text-red-600 text-sm">Failed to load jurisdictions</div>
    );
  }

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
    >
      <option value="">All Jurisdictions</option>
      {jurisdictions?.map((jurisdiction) => (
        <option key={jurisdiction} value={jurisdiction}>
          {jurisdiction}
        </option>
      ))}
    </select>
  );
}

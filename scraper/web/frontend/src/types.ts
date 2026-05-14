export interface Bill {
  id: number;
  source_url: string;
  clean_text?: string;
  excerpt?: string;
  search_term: string;
  domain: string;
  created_at: string;
  text_processing_method?: string;
}

export interface BillsResponse {
  bills: Bill[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface Jurisdiction {
  domain: string;
  signals?: string[];
}

export interface ScrapeConfig {
  terms: string[];
  jurisdictions: Record<string, { signals?: string[] }>;
  start_date?: string;
  end_date?: string;
}

export interface ScrapeJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  config?: ScrapeConfig;
  results?: {
    discovery?: {
      urls?: string[];
    };
    scheduled?: {
      new_urls_found?: number;
      urls_fixed?: number;
    };
  };
  log?: string;
}

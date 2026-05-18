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

export interface ProcessedUrl {
  url: string;
  success: boolean;
  error?: string | null;
}

export interface ScrapeJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  config?: ScrapeConfig;
  runtime_seconds?: number;
  log_size_bytes?: number;
  last_log_update_seconds_ago?: number | null;
  activity_state?: 'active' | 'stalled';
  activity_note?: string;
  results?: {
    total_URLs?: number;
    successful_URLs?: number;
    failed_URLs?: number;
    processed_urls?: ProcessedUrl[];
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

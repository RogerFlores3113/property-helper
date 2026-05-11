export type ListingData = {
  address: string;
  price: number;
  beds: number;
  baths: number;
  amenities: string[];
  source_url: string;
  posted_date: string;
};

export type Listing = {
  id: string;
  job_id: string;
  data: ListingData;
  photo_url: string | null;
  created_at: string;
};

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export type SearchJob = {
  id: string;
  status: JobStatus;
  query: string;
  created_at: string;
  completed_at: string | null;
};

export type JobResponse = { job: SearchJob | null; listings: Listing[] };

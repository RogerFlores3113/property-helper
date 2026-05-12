export type ListingData = {
  address: string | null;
  price: number | null;
  beds: number | null;
  baths: number | null;
  amenities: string[];
  source_url: string;
  posted_date: string | null;
  lat: number | null;
  lng: number | null;
  source_name: string;
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

export type ChipType = 'beds' | 'max_price' | 'min_price' | 'baths' | 'amenity' | 'location';

export type Chip = {
  id: string;
  type: ChipType;
  value: number | string;
  flex: boolean;
};

export type JobPostPayload = {
  query: string;
  chips: Chip[];
  global_flex: boolean;
};

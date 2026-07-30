export interface UserAssetRecord {
  id: string;
  media_type: string;
  platform: string;
  public_url?: string | null;
  created_at?: string;
  [key: string]: unknown;
}

export interface ReferenceUploadResult {
  publicUrl: string;
  s3Key: string;
}

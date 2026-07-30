/** Account and connected-publisher data returned for the signed-in user. */
export interface BusinessProfile {
  company_name: string;
  product_category: string;
  product_description: string;
  target_platforms: string[];
  target_markets: string[];
}

export interface ConnectedSocialAccount {
  name: string;
  icon: string;
  status: string;
}

export interface ZernioConnection {
  has_key: boolean;
  masked_key: string;
  connected: boolean;
  accounts: ConnectedSocialAccount[];
  message: string;
}

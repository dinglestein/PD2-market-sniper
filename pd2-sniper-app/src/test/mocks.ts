// Mock data factories
export const mockStatus = (overrides = {}) => ({
  status: 'running',
  scan_running: false,
  pending_deal: null,
  ...overrides,
});

export const mockDeal = (overrides = {}) => ({
  item_name: 'Rare Vampirebone Gloves',
  price_hr: 2.0,
  seller_name: 'testuser',
  filter_name: 'passive glove +2-20p',
  score: -6.0,
  listing_url: 'https://www.projectdiablo2.com/market/listing/abc123',
  stats: ['+20% IAS', '+10% Pierce', '+66 AR'],
  corruption: ['Corrupted'],
  economy_value_hr: 3.5,
  ...overrides,
});

export const mockEconomy = (overrides = {}) => ({
  refreshed_at: '2026-04-18T07:00:00Z',
  values: {
    'Ber Rune': 2.0,
    'Zod Rune': 4.25,
    'Jah Rune': 2.0,
    'Windforce': 0.25,
    'El Rune': 0.001,
  },
  ...overrides,
});

export const mockPriceCheck = (overrides = {}) => ({
  item_name: 'Windforce',
  median_price: 0.3,
  sample_count: 42,
  confidence: 'high',
  trend: 'stable',
  discount_pct: 17,
  ...overrides,
});

// Fetch mock helper
export function mockFetch(responses: Record<string, any>) {
  return async (url: string, init?: RequestInit) => {
    const method = init?.method || 'GET';
    const key = `${method} ${url}`;

    // Check for exact method+url match first
    if (responses[key]) {
      return {
        ok: true,
        json: async () => responses[key],
      };
    }

    // Check for url-only match
    if (responses[url]) {
      return {
        ok: true,
        json: async () => responses[url],
      };
    }

    // Check for path-only match (without origin)
    const urlObj = new URL(url, 'http://localhost:8420');
    const path = urlObj.pathname;
    if (responses[path]) {
      return {
        ok: true,
        json: async () => responses[path],
      };
    }
    if (responses[`${method} ${path}`]) {
      return {
        ok: true,
        json: async () => responses[`${method} ${path}`],
      };
    }

    return {
      ok: false,
      status: 404,
      json: async () => ({ error: 'Not found' }),
    };
  };
}

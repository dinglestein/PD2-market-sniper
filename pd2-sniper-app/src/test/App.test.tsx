import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App';
import { mockStatus, mockDeal, mockEconomy, mockFetch } from './mocks';

const API = 'http://localhost:8420';

// Helper to set up a working server mock
function mockWorkingServer(extra: Record<string, any> = {}) {
  return vi.spyOn(global, 'fetch').mockImplementation(
    mockFetch({
      [`${API}/api/status`]: mockStatus(),
      [`POST ${API}/api/refresh-dashboard`]: { ok: true },
      [`${API}/assets/scan_results.json`]: { deals: [] },
      [`${API}/assets/all_economy.json`]: mockEconomy(),
      ...extra,
    })
  );
}

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows starting state when server is not reachable', () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));
    render(<App />);
    expect(screen.getByText('Starting Python backend...')).toBeInTheDocument();
  });

  it('shows server online when status responds', async () => {
    mockWorkingServer();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });
  });

  it('renders all four tabs', async () => {
    mockWorkingServer();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Deals')).toBeInTheDocument();
      expect(screen.getByText('Economy')).toBeInTheDocument();
      expect(screen.getByText('Offers')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    }, { timeout: 10000 });
  });

  it('shows no deals message on empty state', async () => {
    mockWorkingServer();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('No deals found yet')).toBeInTheDocument();
    }, { timeout: 10000 });
  });

  it('renders deal cards when deals are available', async () => {
    const deal = mockDeal();
    mockWorkingServer({
      [`${API}/assets/scan_results.json`]: { deals: [deal] },
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(deal.item_name)).toBeInTheDocument();
      expect(screen.getByText(`${deal.price_hr} HR`)).toBeInTheDocument();
      expect(screen.getByText(`👤 ${deal.seller_name}`)).toBeInTheDocument();
    }, { timeout: 10000 });
  });

  it('shows discount badge when economy value > price', async () => {
    const deal = mockDeal({ price_hr: 2.0, economy_value_hr: 3.5 });
    mockWorkingServer({
      [`${API}/assets/scan_results.json`]: { deals: [deal] },
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('-43%')).toBeInTheDocument();
    }, { timeout: 10000 });
  });

  it('expands deal card on click', async () => {
    const deal = mockDeal();
    mockWorkingServer({
      [`${API}/assets/scan_results.json`]: { deals: [deal] },
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(deal.item_name)).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText(deal.item_name));

    await waitFor(() => {
      expect(screen.getByText('Open Listing ↗')).toBeInTheDocument();
      expect(screen.getByText('📊 Price Check')).toBeInTheDocument();
    });
  });

  it('shows economy data in economy tab', async () => {
    const econ = mockEconomy();
    mockWorkingServer();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('Economy'));

    await waitFor(() => {
      expect(screen.getByText('Ber Rune')).toBeInTheDocument();
      expect(screen.getByText('Zod Rune')).toBeInTheDocument();
    });
  });

  it('shows empty economy hint when no data', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(
      mockFetch({
        [`${API}/api/status`]: mockStatus(),
        [`POST ${API}/api/refresh-dashboard`]: { ok: true },
        // No economy data paths
      })
    );
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('Economy'));

    await waitFor(() => {
      expect(screen.getByText(/No economy data loaded/)).toBeInTheDocument();
    });
  });

  it('starts scan when Scan Now is clicked', async () => {
    let scanStarted = false;
    vi.spyOn(global, 'fetch').mockImplementation(async (url: string | URL, init?: RequestInit) => {
      const u = url.toString();
      if (u.includes('/api/status')) {
        return { ok: true, json: async () => mockStatus({ scan_running: scanStarted }) };
      }
      if (u.includes('/api/scan') && init?.method === 'POST') {
        scanStarted = true;
        return { ok: true, json: async () => ({ ok: true, message: 'Scan started' }) };
      }
      if (u.includes('/api/refresh-dashboard')) {
        return { ok: true, json: async () => ({ ok: true }) };
      }
      return { ok: false, status: 404, json: async () => ({ error: 'Not found' }) };
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('🔍 Scan Now'));

    await waitFor(() => {
      expect(screen.getByText(/Stop/)).toBeInTheDocument();
    });
  });

  it('stops scan when Stop button is clicked', async () => {
    let scanRunning = false;
    vi.spyOn(global, 'fetch').mockImplementation(async (url: string | URL, init?: RequestInit) => {
      const u = url.toString();
      if (u.includes('/api/status')) {
        return { ok: true, json: async () => mockStatus({ scan_running: scanRunning }) };
      }
      if (u.includes('/api/scan') && init?.method === 'POST') {
        scanRunning = true;
        return { ok: true, json: async () => ({ ok: true }) };
      }
      if (u.includes('/api/scan-stop') && init?.method === 'POST') {
        scanRunning = false;
        return { ok: true, json: async () => ({ ok: true }) };
      }
      if (u.includes('/api/refresh-dashboard')) {
        return { ok: true, json: async () => ({ ok: true }) };
      }
      return { ok: false, status: 404, json: async () => ({ error: 'Not found' }) };
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();

    // Start scan
    await user.click(screen.getByText('🔍 Scan Now'));
    await waitFor(() => expect(screen.getByText(/Stop/)).toBeInTheDocument());

    // Stop scan
    await user.click(screen.getByText(/Stop/));
    await waitFor(() => {
      expect(screen.getByText('🔍 Scan Now')).toBeInTheDocument();
    });
  });

  it('settings tab shows token input and hotkeys', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(
      mockFetch({
        [`${API}/api/status`]: mockStatus(),
        [`${API}/api/settings/token`]: { token: '' },
        [`POST ${API}/api/refresh-dashboard`]: { ok: true },
      })
    );
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('Settings'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Paste your PD2 JWT token/)).toBeInTheDocument();
      expect(screen.getByText('Save Token')).toBeInTheDocument();
      expect(screen.getByText('Test Connection')).toBeInTheDocument();
      expect(screen.getByText('Get Token ↗')).toBeInTheDocument();
      expect(screen.getByText('⌨️ Hotkeys')).toBeInTheDocument();
      expect(screen.getByText('Start / Stop Scan')).toBeInTheDocument();
    });
  });

  it('search bar filters deals', async () => {
    const deals = [
      mockDeal({ item_name: 'Windforce', seller_name: 'alice' }),
      mockDeal({ item_name: 'Shako', seller_name: 'bob' }),
    ];
    mockWorkingServer({
      [`${API}/assets/scan_results.json`]: { deals },
    });
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Windforce')).toBeInTheDocument();
      expect(screen.getByText('Shako')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    const searchInput = screen.getByPlaceholderText(/Search deals/);
    await user.type(searchInput, 'wind');

    expect(screen.getByText('1 results')).toBeInTheDocument();
    expect(screen.queryByText('Shako')).not.toBeInTheDocument();
  });

  it('deals tab badge shows count', async () => {
    const deals = [mockDeal(), mockDeal({ item_name: 'Shako' }), mockDeal({ item_name: 'Enigma' })];
    mockWorkingServer({
      [`${API}/assets/scan_results.json`]: { deals },
    });
    render(<App />);

    await waitFor(() => {
      // The badge element inside the Deals tab should show "3"
      const badges = screen.getAllByText('3');
      expect(badges.length).toBeGreaterThan(0);
    }, { timeout: 10000 });
  });

  it('offers tab shows instructions', async () => {
    mockWorkingServer();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('Offers'));

    await waitFor(() => {
      expect(screen.getByText('Trade Offers')).toBeInTheDocument();
    });
  });

  it('saves token when Save Token clicked', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(
      mockFetch({
        [`${API}/api/status`]: mockStatus(),
        [`${API}/api/settings/token`]: { token: '' },
        [`POST ${API}/api/settings/token`]: { ok: true },
        [`POST ${API}/api/refresh-dashboard`]: { ok: true },
      })
    );
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Server Online')).toBeInTheDocument();
    }, { timeout: 10000 });

    const user = userEvent.setup();
    await user.click(screen.getByText('Settings'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Paste your PD2 JWT token/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Paste your PD2 JWT token/);
    await user.type(input, 'test-jwt-token-123');

    await user.click(screen.getByText('Save Token'));

    await waitFor(() => {
      expect(screen.getByText('✅ Saved!')).toBeInTheDocument();
    });
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import { useAuthStore } from '../authStore';
import type { User } from '@/types';

// Mock the auth API
vi.mock('@/api/auth', () => ({
  authApi: {
    me: vi.fn(),
  },
}));

// Import the mocked module
import { authApi } from '@/api/auth';

const mockUser: User = {
  id: 1,
  email: 'test@example.com',
  first_name: 'Test',
  last_name: 'User',
  is_active: true,
  is_verified: true,
  is_superuser: false,
  mfa_enabled: false,
  tenant_id: 1,
  created_at: '2024-01-01T00:00:00Z',
};

describe('authStore', () => {
  beforeEach(() => {
    // Reset the store state before each test
    const { logout } = useAuthStore.getState();
    logout();
    useAuthStore.setState({ isLoading: false });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('initial state', () => {
    it('should have correct initial state after reset', () => {
      const state = useAuthStore.getState();

      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.mfaSessionToken).toBeNull();
    });
  });

  describe('setTokens', () => {
    it('should set tokens and mark as authenticated', () => {
      const { setTokens } = useAuthStore.getState();

      act(() => {
        setTokens('access-token-123', 'refresh-token-456');
      });

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe('access-token-123');
      expect(state.refreshToken).toBe('refresh-token-456');
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe('setUser', () => {
    it('should set user data', () => {
      const { setUser } = useAuthStore.getState();

      act(() => {
        setUser(mockUser);
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
    });
  });

  describe('setMfaSessionToken', () => {
    it('should set MFA session token', () => {
      const { setMfaSessionToken } = useAuthStore.getState();

      act(() => {
        setMfaSessionToken('mfa-session-token');
      });

      const state = useAuthStore.getState();
      expect(state.mfaSessionToken).toBe('mfa-session-token');
    });
  });

  describe('logout', () => {
    it('should clear all authentication state', () => {
      const { setTokens, setUser, setMfaSessionToken, logout } = useAuthStore.getState();

      // First set some state
      act(() => {
        setTokens('access-token', 'refresh-token');
        setUser(mockUser);
        setMfaSessionToken('mfa-token');
      });

      // Verify state is set
      expect(useAuthStore.getState().isAuthenticated).toBe(true);

      // Logout
      act(() => {
        logout();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.mfaSessionToken).toBeNull();
    });
  });

  describe('fetchUser', () => {
    it('should fetch and set user on success', async () => {
      vi.mocked(authApi.me).mockResolvedValueOnce(mockUser);

      const { setTokens, fetchUser } = useAuthStore.getState();

      act(() => {
        setTokens('access-token', 'refresh-token');
      });

      await act(async () => {
        await fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(authApi.me).toHaveBeenCalledTimes(1);
    });

    it('should logout on fetch failure', async () => {
      vi.mocked(authApi.me).mockRejectedValueOnce(new Error('Unauthorized'));

      const { setTokens, fetchUser } = useAuthStore.getState();

      act(() => {
        setTokens('access-token', 'refresh-token');
      });

      await act(async () => {
        await fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });
  });

  describe('initialize', () => {
    it('should not fetch user if no token exists', async () => {
      const { initialize } = useAuthStore.getState();

      await act(async () => {
        await initialize();
      });

      expect(authApi.me).not.toHaveBeenCalled();
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('should fetch user if token exists', async () => {
      vi.mocked(authApi.me).mockResolvedValueOnce(mockUser);

      // Set token directly in state
      useAuthStore.setState({ accessToken: 'existing-token' });

      const { initialize } = useAuthStore.getState();

      await act(async () => {
        await initialize();
      });

      expect(authApi.me).toHaveBeenCalledTimes(1);
      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('should logout if token validation fails', async () => {
      vi.mocked(authApi.me).mockRejectedValueOnce(new Error('Token expired'));

      // Set token directly in state
      useAuthStore.setState({ accessToken: 'expired-token', isAuthenticated: true });

      const { initialize } = useAuthStore.getState();

      await act(async () => {
        await initialize();
      });

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.accessToken).toBeNull();
      expect(state.isLoading).toBe(false);
    });
  });

  describe('authentication flow', () => {
    it('should handle complete login flow', async () => {
      vi.mocked(authApi.me).mockResolvedValueOnce(mockUser);

      const { setTokens, fetchUser } = useAuthStore.getState();

      // 1. Set tokens after login
      act(() => {
        setTokens('new-access-token', 'new-refresh-token');
      });

      expect(useAuthStore.getState().isAuthenticated).toBe(true);

      // 2. Fetch user profile
      await act(async () => {
        await fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it('should handle MFA flow', () => {
      const { setMfaSessionToken, setTokens, setUser } = useAuthStore.getState();

      // 1. Login returns MFA required
      act(() => {
        setMfaSessionToken('mfa-session-123');
      });

      expect(useAuthStore.getState().mfaSessionToken).toBe('mfa-session-123');
      expect(useAuthStore.getState().isAuthenticated).toBe(false);

      // 2. MFA verification succeeds
      act(() => {
        setTokens('access-token', 'refresh-token');
        setUser(mockUser);
      });

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(mockUser);
    });
  });
});

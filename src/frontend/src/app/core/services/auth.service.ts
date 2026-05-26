import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AuthUser {
  id: string;
  email: string;
  nome_completo: string;
  roles: string[];
  is_mfa_enabled: boolean;
}

interface LoginResponse {
  access_token: string;
  user: AuthUser;
}

interface MfaRequiredResponse {
  mfa_required: true;
  mfa_token: string;
}

interface RefreshResponse {
  access_token: string;
}

interface AuthState {
  user: AuthUser | null;
  token: string | null;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly apiUrl = environment.apiBaseUrl;

  private refreshing: Promise<string | null> | null = null;

  readonly authState = signal<AuthState>({ user: null, token: null });
  readonly isAuthenticated = computed(() => !!this.authState().token);
  readonly currentUser = computed(() => this.authState().user);

  async login(email: string, password: string): Promise<void> {
    const response = await firstValueFrom(
      this.http.post<LoginResponse | MfaRequiredResponse>(
        `${this.apiUrl}/auth/login`,
        { email, password },
        { withCredentials: true },
      ),
    );

    if ('mfa_required' in response && response.mfa_required) {
      throw new MfaRequiredError(response.mfa_token);
    }

    const loginResp = response as LoginResponse;
    this.authState.set({
      user: loginResp.user,
      token: loginResp.access_token,
    });
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${this.apiUrl}/auth/logout`, {}, { withCredentials: true }),
      );
    } catch {
      // Ignore errors during logout
    }
    this.authState.set({ user: null, token: null });
    this.router.navigate(['/auth/login']);
  }

  async refreshToken(): Promise<string | null> {
    // Lock: only one refresh at a time
    if (this.refreshing) {
      return this.refreshing;
    }

    this.refreshing = this.doRefresh();
    try {
      return await this.refreshing;
    } finally {
      this.refreshing = null;
    }
  }

  private async doRefresh(): Promise<string | null> {
    try {
      const response = await firstValueFrom(
        this.http.post<RefreshResponse>(
          `${this.apiUrl}/auth/refresh`,
          {},
          { withCredentials: true },
        ),
      );
      this.authState.update((state) => ({
        ...state,
        token: response.access_token,
      }));

      // Load user profile with the new token
      await this.loadUser(response.access_token);

      return response.access_token;
    } catch {
      this.authState.set({ user: null, token: null });
      return null;
    }
  }

  private async loadUser(token: string): Promise<void> {
    try {
      const user = await firstValueFrom(
        this.http.get<AuthUser>(`${this.apiUrl}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      );
      this.authState.update((state) => ({ ...state, user }));
    } catch {
      // Token valid but user fetch failed — keep token, user will be null
    }
  }

  /**
   * Called on app init — tries to restore session from refresh cookie.
   */
  async tryRestoreSession(): Promise<void> {
    // Only attempt refresh on routes that need auth (skip auth pages)
    const path = window.location.pathname;
    if (path.startsWith('/auth/')) {
      return;
    }
    await this.refreshToken();
  }

  getToken(): string | null {
    return this.authState().token;
  }
}

export class MfaRequiredError extends Error {
  constructor(public readonly mfaToken: string) {
    super('MFA required');
  }
}

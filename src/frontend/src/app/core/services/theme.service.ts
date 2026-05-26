import { Injectable, signal, effect, computed, inject, PLATFORM_ID, DestroyRef } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type ThemeMode = 'light' | 'dark' | 'system';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly STORAGE_KEY = 'theme';
  private readonly platformId = inject(PLATFORM_ID);
  private readonly destroyRef = inject(DestroyRef);
  private readonly isBrowser = isPlatformBrowser(this.platformId);

  readonly theme = signal<ThemeMode>(this.loadTheme());

  readonly resolvedTheme = computed<'light' | 'dark'>(() => {
    const mode = this.theme();
    if (mode === 'system') {
      return this.isBrowser && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
    }
    return mode;
  });

  readonly themeIcon = computed(() => {
    const t = this.theme();
    if (t === 'light') return 'heroSun';
    if (t === 'dark') return 'heroMoon';
    return 'heroComputerDesktop';
  });

  constructor() {
    effect(() => {
      const mode = this.theme();
      if (this.isBrowser) {
        localStorage.setItem(this.STORAGE_KEY, mode);
        this.applyTheme(mode);
      }
    });

    if (this.isBrowser) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handler = () => {
        if (this.theme() === 'system') {
          this.applyTheme('system');
        }
      };
      mediaQuery.addEventListener('change', handler);
      this.destroyRef.onDestroy(() => mediaQuery.removeEventListener('change', handler));
    }
  }

  setTheme(mode: ThemeMode): void {
    this.theme.set(mode);
  }

  toggle(): void {
    const current = this.theme();
    if (current === 'light') this.setTheme('dark');
    else if (current === 'dark') this.setTheme('system');
    else this.setTheme('light');
  }

  private loadTheme(): ThemeMode {
    if (!this.isBrowser) return 'system';
    const stored = localStorage.getItem(this.STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
    return 'system';
  }

  private applyTheme(mode: ThemeMode): void {
    if (!this.isBrowser) return;
    const isDark =
      mode === 'dark' ||
      (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }
}

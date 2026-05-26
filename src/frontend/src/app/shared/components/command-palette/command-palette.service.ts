import { Injectable, signal } from '@angular/core';

const RECENT_KEY = 'command-palette-recent';
const MAX_RECENT = 10;

@Injectable({ providedIn: 'root' })
export class CommandPaletteService {
  readonly isOpen = signal(false);

  open(): void {
    this.isOpen.set(true);
  }

  close(): void {
    this.isOpen.set(false);
  }

  toggle(): void {
    this.isOpen.update((v) => !v);
  }

  getRecentSearches(): string[] {
    try {
      const raw = localStorage.getItem(RECENT_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  addRecentSearch(query: string): void {
    const trimmed = query.trim();
    if (!trimmed) return;
    const recent = this.getRecentSearches().filter((r) => r !== trimmed);
    recent.unshift(trimmed);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
  }

  clearRecentSearches(): void {
    localStorage.removeItem(RECENT_KEY);
  }
}

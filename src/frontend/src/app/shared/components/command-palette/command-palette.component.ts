import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  effect,
} from '@angular/core';
import { Router } from '@angular/router';
import { UiIconComponent } from '../icon/icon.component';
import { CommandPaletteService } from './command-palette.service';
import { SearchService, SearchResultItem } from '../../../core/services/search.service';

interface GroupedResults {
  label: string;
  type: string;
  items: SearchResultItem[];
}

@Component({
  selector: 'app-command-palette',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CommandPaletteComponent implements AfterViewInit, OnDestroy {
  private readonly paletteService = inject(CommandPaletteService);
  private readonly searchService = inject(SearchService);
  private readonly router = inject(Router);

  readonly isOpen = this.paletteService.isOpen;
  readonly query = signal('');
  readonly results = signal<SearchResultItem[]>([]);
  readonly isSearching = signal(false);
  readonly selectedIndex = signal(0);
  readonly recentSearches = signal<string[]>([]);

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;

  @ViewChild('searchInput') searchInputRef!: ElementRef<HTMLInputElement>;

  readonly groupedResults = computed<GroupedResults[]>(() => {
    const items = this.results();
    const typeLabels: Record<string, string> = {
      customer: 'Clientes',
      vehicle: 'Veiculos',
      contract: 'Contratos',
    };
    const groups: Record<string, SearchResultItem[]> = {};
    for (const item of items) {
      if (!groups[item.type]) groups[item.type] = [];
      groups[item.type].push(item);
    }
    return Object.entries(groups).map(([type, items]) => ({
      label: typeLabels[type] ?? type,
      type,
      items,
    }));
  });

  readonly flatResults = computed(() => this.results());

  readonly isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);
  readonly shortcutLabel = this.isMac ? 'Cmd+K' : 'Ctrl+K';

  constructor() {
    // Focus input when opened
    effect(() => {
      if (this.isOpen()) {
        this.recentSearches.set(this.paletteService.getRecentSearches());
        this.query.set('');
        this.results.set([]);
        this.selectedIndex.set(0);
        // Use setTimeout to wait for DOM
        setTimeout(() => {
          this.searchInputRef?.nativeElement?.focus();
        }, 50);
      }
    });
  }

  ngAfterViewInit(): void {
    // Global keyboard shortcut
    this.keydownHandler = (e: KeyboardEvent) => {
      const isMod = this.isMac ? e.metaKey : e.ctrlKey;
      if (isMod && e.key === 'k') {
        e.preventDefault();
        this.paletteService.toggle();
      }
    };
    document.addEventListener('keydown', this.keydownHandler);
  }

  ngOnDestroy(): void {
    if (this.keydownHandler) {
      document.removeEventListener('keydown', this.keydownHandler);
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
  }

  onInput(value: string): void {
    this.query.set(value);
    this.selectedIndex.set(0);

    if (this.debounceTimer) clearTimeout(this.debounceTimer);

    if (!value.trim()) {
      this.results.set([]);
      return;
    }

    this.debounceTimer = setTimeout(() => {
      this.search(value.trim());
    }, 200);
  }

  async search(q: string): Promise<void> {
    this.isSearching.set(true);
    try {
      const resp = await this.searchService.globalSearch(q);
      this.results.set(resp.results);
    } catch {
      this.results.set([]);
    } finally {
      this.isSearching.set(false);
    }
  }

  onKeydown(event: KeyboardEvent): void {
    const flat = this.flatResults();
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.selectedIndex.update((i) => Math.min(i + 1, flat.length - 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.selectedIndex.update((i) => Math.max(i - 1, 0));
        break;
      case 'Enter': {
        event.preventDefault();
        const item = flat[this.selectedIndex()];
        if (item) this.selectResult(item);
        break;
      }
      case 'Escape':
        this.close();
        break;
    }
  }

  selectResult(item: SearchResultItem): void {
    this.paletteService.addRecentSearch(this.query());
    this.close();
    this.router.navigateByUrl(item.url);
  }

  selectRecent(q: string): void {
    this.query.set(q);
    this.search(q);
  }

  close(): void {
    this.paletteService.close();
  }

  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('palette-backdrop')) {
      this.close();
    }
  }

  typeIcon(type: string): string {
    switch (type) {
      case 'customer':
        return 'heroUsers';
      case 'vehicle':
        return 'heroTruck';
      case 'contract':
        return 'heroDocumentText';
      default:
        return 'heroMagnifyingGlass';
    }
  }

  getItemIndex(item: SearchResultItem): number {
    return this.flatResults().indexOf(item);
  }
}

import {
  Component,
  ChangeDetectionStrategy,
  ElementRef,
  ViewChild,
  computed,
  input,
  output,
  signal,
  AfterViewInit,
  OnInit,
  OnDestroy,
} from '@angular/core';
import {
  CdkOverlayOrigin,
  CdkConnectedOverlay,
  ConnectedPosition,
} from '@angular/cdk/overlay';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { UiIconComponent } from '../icon/icon.component';

export interface SearchableOption {
  value: string;
  label: string;
  subtitle?: string;
  disabled?: boolean;
}

@Component({
  selector: 'app-searchable-select',
  standalone: true,
  imports: [CdkOverlayOrigin, CdkConnectedOverlay, UiIconComponent],
  templateUrl: './searchable-select.component.html',
  styleUrl: './searchable-select.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchableSelectComponent implements OnInit, AfterViewInit, OnDestroy {
  /** Static options (for small lists) */
  readonly options = input<SearchableOption[]>([]);

  /** Current selected value */
  readonly value = input<string>('');

  /** Display label for selected value (when options are server-loaded) */
  readonly selectedLabel = input<string>('');

  readonly placeholder = input<string>('Buscar...');
  readonly disabled = input<boolean>(false);
  readonly required = input<boolean>(false);
  readonly loading = input<boolean>(false);

  /** Minimum chars to trigger search */
  readonly minChars = input<number>(2);

  /** Emits selected value */
  readonly valueChange = output<string>();

  /** Emits search term (debounced) — parent does the API call */
  readonly searchChange = output<string>();

  /** Emits when user clears selection */
  readonly cleared = output<void>();

  readonly isOpen = signal(false);
  readonly searchQuery = signal('');
  readonly highlightedIndex = signal(-1);
  readonly triggerWidth = signal(0);

  private readonly searchSubject = new Subject<string>();
  private searchSub: { unsubscribe(): void } | null = null;

  readonly dropdownPositions: ConnectedPosition[] = [
    { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top', offsetY: 4 },
    { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom', offsetY: -4 },
  ];

  @ViewChild('triggerEl') triggerEl!: ElementRef<HTMLButtonElement>;
  @ViewChild('searchInput') searchInput?: ElementRef<HTMLInputElement>;

  private resizeObserver?: ResizeObserver;

  readonly displayValue = computed(() => {
    if (this.selectedLabel()) return this.selectedLabel();
    const opt = this.options().find((o) => o.value === this.value());
    return opt?.label ?? '';
  });

  readonly hasSelection = computed(() => !!this.value());

  ngOnInit(): void {
    this.searchSub = this.searchSubject
      .pipe(debounceTime(300), distinctUntilChanged())
      .subscribe((term) => {
        this.searchChange.emit(term);
      });
  }

  ngAfterViewInit(): void {
    this.resizeObserver = new ResizeObserver(() => {
      if (this.isOpen()) {
        this.refreshWidth();
      }
    });
    this.resizeObserver.observe(this.triggerEl.nativeElement);
  }

  ngOnDestroy(): void {
    this.searchSub?.unsubscribe();
    this.resizeObserver?.disconnect();
  }

  open(): void {
    if (this.disabled()) return;
    this.refreshWidth();
    this.searchQuery.set('');
    this.highlightedIndex.set(-1);
    this.isOpen.set(true);
    setTimeout(() => this.searchInput?.nativeElement.focus());
  }

  refreshWidth(): void {
    this.triggerWidth.set(this.triggerEl.nativeElement.getBoundingClientRect().width);
  }

  close(): void {
    this.isOpen.set(false);
  }

  onBackdropClick(): void {
    this.close();
  }

  onSearchInput(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.searchQuery.set(val);
    if (val.length >= this.minChars()) {
      this.searchSubject.next(val);
    }
  }

  select(opt: SearchableOption): void {
    if (opt.disabled) return;
    this.valueChange.emit(opt.value);
    this.close();
  }

  clear(event: Event): void {
    event.stopPropagation();
    this.cleared.emit();
    this.valueChange.emit('');
  }

  onKeydown(event: KeyboardEvent): void {
    const opts = this.options();
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.highlightedIndex.update((i) => Math.min(i + 1, opts.length - 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.highlightedIndex.update((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        event.preventDefault();
        {
          const idx = this.highlightedIndex();
          if (idx >= 0 && idx < opts.length) this.select(opts[idx]);
        }
        break;
      case 'Escape':
        this.close();
        break;
    }
  }

  isSelected(opt: SearchableOption): boolean {
    return this.value() === opt.value;
  }

  isHighlighted(opt: SearchableOption): boolean {
    const idx = this.highlightedIndex();
    const opts = this.options();
    return idx >= 0 && idx < opts.length && opts[idx] === opt;
  }
}

import {
  Component,
  ChangeDetectionStrategy,
  ElementRef,
  ViewChild,
  computed,
  input,
  model,
  signal,
} from '@angular/core';
import { KeyValuePipe } from '@angular/common';
import {
  CdkOverlayOrigin,
  CdkConnectedOverlay,
  ConnectedPosition,
} from '@angular/cdk/overlay';
import { UiIconComponent } from '../icon/icon.component';

export interface SelectOption {
  value: string;
  label: string;
  group?: string;
  icon?: string;
  disabled?: boolean;
}

@Component({
  selector: 'app-select',
  standalone: true,
  imports: [KeyValuePipe, CdkOverlayOrigin, CdkConnectedOverlay, UiIconComponent],
  templateUrl: './custom-select.component.html',
  styleUrl: './custom-select.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CustomSelectComponent {
  readonly options = input.required<SelectOption[]>();
  readonly value = model<string>('');
  readonly placeholder = input<string>('Selecione...');
  readonly disabled = input<boolean>(false);
  readonly required = input<boolean>(false);

  readonly isOpen = signal(false);
  readonly searchQuery = signal('');
  readonly highlightedIndex = signal(-1);
  readonly triggerWidth = signal(0);

  readonly dropdownPositions: ConnectedPosition[] = [
    { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top', offsetY: 4 },
    { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom', offsetY: -4 },
  ];

  @ViewChild('triggerBtn') triggerBtn!: ElementRef<HTMLButtonElement>;
  @ViewChild('searchInput') searchInput?: ElementRef<HTMLInputElement>;

  readonly selectedOption = computed(
    () => this.options().find((o) => o.value === this.value()) ?? null,
  );

  readonly displayLabel = computed(
    () => this.selectedOption()?.label ?? this.placeholder(),
  );

  readonly filteredOptions = computed(() => {
    const q = this.searchQuery().toLowerCase().trim();
    if (!q) return this.options();
    return this.options().filter((o) => o.label.toLowerCase().includes(q));
  });

  readonly showSearch = computed(() => this.options().length > 6);

  readonly hasGroups = computed(() => this.options().some((o) => !!o.group));

  readonly groups = computed(() => {
    const opts = this.filteredOptions();
    const groupMap = new Map<string, SelectOption[]>();
    for (const opt of opts) {
      const g = opt.group ?? '';
      if (!groupMap.has(g)) groupMap.set(g, []);
      groupMap.get(g)!.push(opt);
    }
    return groupMap;
  });

  toggle(): void {
    if (this.disabled()) return;
    if (!this.isOpen()) {
      this.triggerWidth.set(
        this.triggerBtn.nativeElement.getBoundingClientRect().width,
      );
      this.searchQuery.set('');
      this.highlightedIndex.set(-1);
    }
    this.isOpen.update((v) => !v);
    if (this.isOpen()) {
      setTimeout(() => this.searchInput?.nativeElement.focus());
    }
  }

  select(opt: SelectOption): void {
    if (opt.disabled) return;
    this.value.set(opt.value);
    this.isOpen.set(false);
  }

  onBackdropClick(): void {
    this.isOpen.set(false);
  }

  onSearchInput(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.searchQuery.set(val);
    this.highlightedIndex.set(-1);
  }

  onKeydown(event: KeyboardEvent): void {
    const opts = this.filteredOptions();
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
        this.isOpen.set(false);
        break;
    }
  }

  isSelected(opt: SelectOption): boolean {
    return this.value() === opt.value;
  }

  isHighlighted(opt: SelectOption): boolean {
    const idx = this.highlightedIndex();
    const opts = this.filteredOptions();
    return idx >= 0 && idx < opts.length && opts[idx] === opt;
  }
}

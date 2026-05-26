import { Component, ChangeDetectionStrategy, input } from '@angular/core';

@Component({
  selector: 'ui-skeleton',
  standalone: true,
  template: `
    @switch (variant()) {
      @case ('card') {
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 animate-pulse">
          <div class="h-4 w-2/3 bg-[var(--border-subtle)] rounded mb-4"></div>
          <div class="h-3 w-1/2 bg-[var(--border-subtle)] rounded mb-2"></div>
          <div class="h-3 w-1/3 bg-[var(--border-subtle)] rounded"></div>
        </div>
      }
      @case ('table-row') {
        <div class="flex items-center gap-4 px-4 py-3 animate-pulse border-b border-[var(--border)]">
          <div class="h-4 w-24 bg-[var(--border-subtle)] rounded"></div>
          <div class="h-4 w-32 bg-[var(--border-subtle)] rounded"></div>
          <div class="h-4 w-20 bg-[var(--border-subtle)] rounded"></div>
          <div class="flex-1"></div>
          <div class="h-4 w-16 bg-[var(--border-subtle)] rounded"></div>
        </div>
      }
      @case ('text') {
        <div class="animate-pulse space-y-2">
          <div class="h-4 w-full bg-[var(--border-subtle)] rounded"></div>
          <div class="h-4 w-3/4 bg-[var(--border-subtle)] rounded"></div>
        </div>
      }
      @case ('chart') {
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 animate-pulse">
          <div class="h-4 w-24 bg-[var(--border-subtle)] rounded mb-4"></div>
          <div class="h-40 bg-[var(--border-subtle)] rounded-xl"></div>
        </div>
      }
      @default {
        <div class="animate-pulse">
          <div class="h-4 bg-[var(--border-subtle)] rounded" [style.width]="width()"></div>
        </div>
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkeletonLoaderComponent {
  variant = input<'card' | 'table-row' | 'text' | 'chart' | 'default'>('default');
  width = input<string>('100%');
}

import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { UiIconComponent } from '../icon/icon.component';

@Component({
  selector: 'ui-empty-state',
  standalone: true,
  imports: [UiIconComponent, RouterLink],
  template: `
    <div class="flex flex-col items-center justify-center py-16 text-[var(--text-muted)]">
      <ui-icon [name]="icon()" size="3rem" />
      <h3 class="mt-4 text-lg font-medium text-[var(--text-primary)]">{{ title() }}</h3>
      @if (description()) {
        <p class="mt-1 text-sm text-center max-w-sm">{{ description() }}</p>
      }
      @if (ctaLabel() && ctaRoute()) {
        <a
          [routerLink]="ctaRoute()"
          class="mt-4 flex items-center gap-2 rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 transition"
        >
          <ui-icon name="heroPlus" size="1rem" />
          {{ ctaLabel() }}
        </a>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EmptyStateComponent {
  icon = input<string>('heroFolderOpen');
  title = input.required<string>();
  description = input<string>('');
  ctaLabel = input<string>('');
  ctaRoute = input<string>('');
}

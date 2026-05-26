import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { UiIconComponent } from '../icon/icon.component';

export interface Breadcrumb {
  label: string;
  route?: string;
}

@Component({
  selector: 'ui-breadcrumbs',
  standalone: true,
  imports: [RouterLink, UiIconComponent],
  template: `
    <nav class="flex items-center gap-1 text-sm text-[var(--text-muted)]" aria-label="Breadcrumb">
      @for (crumb of items(); track crumb.label; let last = $last) {
        @if (crumb.route && !last) {
          <a
            [routerLink]="crumb.route"
            class="hover:text-[var(--text-primary)] transition"
          >
            {{ crumb.label }}
          </a>
        } @else {
          <span [class.text-[var(--text-primary)]]="last" [class.font-medium]="last">
            {{ crumb.label }}
          </span>
        }
        @if (!last) {
          <ui-icon name="heroChevronRight" size="0.75rem" />
        }
      }
    </nav>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BreadcrumbsComponent {
  items = input.required<Breadcrumb[]>();
}

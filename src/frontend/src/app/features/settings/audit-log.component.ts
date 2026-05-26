import { Component, ChangeDetectionStrategy, inject, signal, OnInit, computed } from '@angular/core';
import { DatePipe, SlicePipe } from '@angular/common';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import { AdminService, AuditLogEntry } from '../../core/services/admin.service';

@Component({
  selector: 'app-audit-log',
  standalone: true,
  imports: [UiIconComponent, DatePipe, SlicePipe],
  templateUrl: './audit-log.component.html',
  styleUrl: './audit-log.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuditLogComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly toastService = inject(ToastService);

  readonly entries = signal<AuditLogEntry[]>([]);
  readonly isLoading = signal(true);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(25);
  readonly expandedId = signal<number | null>(null);

  // Filters
  readonly filterAction = signal('');
  readonly filterEntity = signal('');
  readonly filterUserId = signal('');
  readonly filterDateFrom = signal('');
  readonly filterDateTo = signal('');

  readonly totalPages = computed(() => Math.ceil(this.total() / this.size()) || 1);

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.isLoading.set(true);
    try {
      const data = await this.adminService.searchAuditLog({
        action: this.filterAction() || undefined,
        entity: this.filterEntity() || undefined,
        user_id: this.filterUserId() || undefined,
        date_from: this.filterDateFrom() || undefined,
        date_to: this.filterDateTo() || undefined,
        page: this.page(),
        size: this.size(),
      });
      this.entries.set(data.items);
      this.total.set(data.total);
    } catch {
      this.toastService.show({ message: 'Erro ao carregar log de auditoria', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  async applyFilters(): Promise<void> {
    this.page.set(1);
    await this.load();
  }

  async clearFilters(): Promise<void> {
    this.filterAction.set('');
    this.filterEntity.set('');
    this.filterUserId.set('');
    this.filterDateFrom.set('');
    this.filterDateTo.set('');
    this.page.set(1);
    await this.load();
  }

  async goToPage(p: number): Promise<void> {
    if (p < 1 || p > this.totalPages()) return;
    this.page.set(p);
    await this.load();
  }

  toggleExpand(id: number): void {
    this.expandedId.set(this.expandedId() === id ? null : id);
  }

  formatJson(obj: Record<string, unknown> | null): string {
    if (!obj) return '—';
    return JSON.stringify(obj, null, 2);
  }

  severityClass(severity: string): string {
    switch (severity) {
      case 'critical':
        return 'bg-red-500/15 text-red-400';
      case 'warning':
        return 'bg-yellow-500/15 text-yellow-400';
      default:
        return 'bg-blue-500/15 text-blue-400';
    }
  }
}

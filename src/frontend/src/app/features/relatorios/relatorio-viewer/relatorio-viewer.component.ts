import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import {
  ReportService,
  ReportColumn,
  ReportRow,
} from '../../../core/services/report.service';

@Component({
  selector: 'app-relatorio-viewer',
  standalone: true,
  imports: [UiIconComponent, FormsModule],
  templateUrl: './relatorio-viewer.component.html',
  styleUrl: './relatorio-viewer.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RelatorioViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly reportService = inject(ReportService);

  readonly slug = signal('');
  readonly reportName = signal('');
  readonly columns = signal<ReportColumn[]>([]);
  readonly rows = signal<ReportRow[]>([]);
  readonly total = signal(0);
  readonly isLoading = signal(true);
  readonly isExporting = signal(false);

  // Filters
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly statusFilter = signal('');

  ngOnInit(): void {
    const type = this.route.snapshot.paramMap.get('type') ?? '';
    this.slug.set(type);

    // Find report name
    const def = this.reportService.builtInReports.find(
      (r) => r.slug === type,
    );
    this.reportName.set(def?.name ?? type);

    this.loadReport();
  }

  async loadReport(): Promise<void> {
    this.isLoading.set(true);
    try {
      const params: Record<string, string> = {};
      if (this.dateFrom()) params['date_from'] = this.dateFrom();
      if (this.dateTo()) params['date_to'] = this.dateTo();
      if (this.statusFilter()) params['status'] = this.statusFilter();

      const data = await this.reportService.getReport(this.slug(), params);
      this.columns.set(data.columns);
      this.rows.set(data.rows);
      this.total.set(data.total);
    } catch {
      // Show empty state
      this.columns.set([]);
      this.rows.set([]);
    } finally {
      this.isLoading.set(false);
    }
  }

  applyFilters(): void {
    this.loadReport();
  }

  async exportCsv(): Promise<void> {
    this.isExporting.set(true);
    try {
      const params: Record<string, string> = {};
      if (this.dateFrom()) params['date_from'] = this.dateFrom();
      if (this.dateTo()) params['date_to'] = this.dateTo();
      if (this.statusFilter()) params['status'] = this.statusFilter();

      const blob = await this.reportService.exportCsv(this.slug(), params);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${this.slug()}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // Ignore
    } finally {
      this.isExporting.set(false);
    }
  }

  goBack(): void {
    this.router.navigate(['/sistema/reports']);
  }

  formatCell(value: string, format: string): string {
    if (!value || value === 'None') return '-';
    if (format === 'currency') {
      const num = parseFloat(value);
      if (isNaN(num)) return value;
      return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
      }).format(num);
    }
    if (format === 'percent') {
      return `${value}%`;
    }
    return value;
  }
}

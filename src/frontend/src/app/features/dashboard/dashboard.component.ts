import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { Router } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import {
  DashboardService,
  DashboardSummary,
  ReceivablesTrendPoint,
  AgingBucket,
  TopDefaulter,
} from '../../core/services/dashboard.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: '../dashboard/dashboard.component.html',
  styleUrl: '../dashboard/dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit {
  private readonly dashboardService = inject(DashboardService);
  private readonly router = inject(Router);

  readonly isLoading = signal(true);
  readonly summary = signal<DashboardSummary | null>(null);
  readonly trend = signal<ReceivablesTrendPoint[]>([]);
  readonly aging = signal<AgingBucket[]>([]);
  readonly defaulters = signal<TopDefaulter[]>([]);
  readonly period = signal<'month' | '3months' | 'year'>('month');

  ngOnInit(): void {
    this.loadData();
  }

  async loadData(): Promise<void> {
    this.isLoading.set(true);
    try {
      const [summaryData, trendData, agingData, defaultersData] =
        await Promise.all([
          this.dashboardService.getSummary(),
          this.dashboardService.getReceivablesTrend(12),
          this.dashboardService.getOverdueAging(),
          this.dashboardService.getTopDefaulters(10),
        ]);
      this.summary.set(summaryData);
      this.trend.set(trendData.data);
      this.aging.set(agingData.buckets);
      this.defaulters.set(defaultersData.items);
    } catch {
      // Silently handle — show empty state
    } finally {
      this.isLoading.set(false);
    }
  }

  setPeriod(p: 'month' | '3months' | 'year'): void {
    this.period.set(p);
    this.loadData();
  }

  // Chart helpers
  trendMax(): number {
    const data = this.trend();
    if (!data.length) return 1;
    return Math.max(...data.map((d) => Math.max(d.total_due, d.total_received))) || 1;
  }

  agingMax(): number {
    const data = this.aging();
    if (!data.length) return 1;
    return Math.max(...data.map((d) => d.amount)) || 1;
  }

  barHeight(value: number, max: number): number {
    return max > 0 ? Math.round((value / max) * 100) : 0;
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatShort(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(0)}k`;
    return value.toFixed(0);
  }

  navigateTo(route: string): void {
    this.router.navigate([route]);
  }

  navigateToCustomer(id: string): void {
    this.router.navigate(['/sistema/clientes', id]);
  }
}

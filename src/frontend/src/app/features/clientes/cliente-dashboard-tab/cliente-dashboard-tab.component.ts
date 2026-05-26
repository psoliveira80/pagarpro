import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  OnInit,
} from '@angular/core';
import {
  DashboardService,
  CustomerDashboard,
} from '../../../core/services/dashboard.service';

@Component({
  selector: 'app-cliente-dashboard-tab',
  standalone: true,
  templateUrl: './cliente-dashboard-tab.component.html',
  styleUrl: './cliente-dashboard-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ClienteDashboardTabComponent implements OnInit {
  customerId = input.required<string>();

  private readonly dashboardService = inject(DashboardService);

  readonly data = signal<CustomerDashboard | null>(null);
  readonly isLoading = signal(true);
  readonly error = signal(false);

  ngOnInit(): void {
    this.loadData();
  }

  async loadData(): Promise<void> {
    this.isLoading.set(true);
    this.error.set(false);
    try {
      const result = await this.dashboardService.getCustomerDashboard(
        this.customerId(),
      );
      this.data.set(result);
    } catch {
      this.error.set(true);
    } finally {
      this.isLoading.set(false);
    }
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  scoreColor(score: number): string {
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }

  scoreBg(score: number): string {
    if (score >= 80) return 'bg-green-500/20';
    if (score >= 50) return 'bg-yellow-500/20';
    return 'bg-red-500/20';
  }

  gaugePercent(score: number): number {
    return Math.min(100, Math.max(0, score));
  }
}

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
  VehicleDashboard,
} from '../../../core/services/dashboard.service';

@Component({
  selector: 'app-veiculo-dashboard-tab',
  standalone: true,
  templateUrl: './veiculo-dashboard-tab.component.html',
  styleUrl: './veiculo-dashboard-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VeiculoDashboardTabComponent implements OnInit {
  vehicleId = input.required<string>();

  private readonly dashboardService = inject(DashboardService);

  readonly data = signal<VehicleDashboard | null>(null);
  readonly isLoading = signal(true);
  readonly error = signal(false);

  ngOnInit(): void {
    this.loadData();
  }

  async loadData(): Promise<void> {
    this.isLoading.set(true);
    this.error.set(false);
    try {
      const result = await this.dashboardService.getVehicleDashboard(
        this.vehicleId(),
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

  roiColor(roi: number): string {
    if (roi >= 20) return 'text-green-400';
    if (roi >= 0) return 'text-yellow-400';
    return 'text-red-400';
  }

  revenuePercent(revenue: number, investment: number): number {
    if (investment <= 0) return 0;
    return Math.min(100, (revenue / investment) * 100);
  }
}

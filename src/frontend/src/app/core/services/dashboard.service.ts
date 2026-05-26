import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface DashboardSummary {
  total_receivable: number;
  total_overdue: number;
  received_this_month: number;
  active_contracts: number;
  fleet_value: number;
  overdue_percent: number;
}

export interface ReceivablesTrendPoint {
  period: string;
  total_due: number;
  total_received: number;
  total_overdue: number;
}

export interface AgingBucket {
  bucket: string;
  count: number;
  amount: number;
}

export interface TopDefaulter {
  customer_id: string;
  customer_name: string;
  overdue_amount: number;
  overdue_count: number;
  score: number;
}

export interface CustomerDashboard {
  customer_id: string;
  customer_name: string;
  total_contracted: number;
  total_paid: number;
  total_open: number;
  total_overdue: number;
  score: number;
  punctuality_percent: number;
  active_contracts: number;
}

export interface VehicleDashboard {
  vehicle_id: string;
  display_name: string;
  purchase_value: number;
  fipe_value: number;
  total_revenue: number;
  total_expenses: number;
  roi_percent: number;
  accumulated_profit: number;
  in_service_since: string | null;
}

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/dashboard`;

  async getSummary(): Promise<DashboardSummary> {
    return firstValueFrom(
      this.http.get<DashboardSummary>(`${this.baseUrl}/summary`),
    );
  }

  async getReceivablesTrend(months = 12): Promise<{ data: ReceivablesTrendPoint[] }> {
    const params = new HttpParams().set('months', months.toString());
    return firstValueFrom(
      this.http.get<{ data: ReceivablesTrendPoint[] }>(
        `${this.baseUrl}/charts/receivables-trend`,
        { params },
      ),
    );
  }

  async getOverdueAging(): Promise<{ buckets: AgingBucket[] }> {
    return firstValueFrom(
      this.http.get<{ buckets: AgingBucket[] }>(
        `${this.baseUrl}/charts/overdue-aging`,
      ),
    );
  }

  async getTopDefaulters(limit = 10): Promise<{ items: TopDefaulter[] }> {
    const params = new HttpParams().set('limit', limit.toString());
    return firstValueFrom(
      this.http.get<{ items: TopDefaulter[] }>(
        `${this.baseUrl}/charts/top-defaulters`,
        { params },
      ),
    );
  }

  async getCustomerDashboard(customerId: string): Promise<CustomerDashboard> {
    return firstValueFrom(
      this.http.get<CustomerDashboard>(`${this.baseUrl}/customer/${customerId}`),
    );
  }

  async getVehicleDashboard(vehicleId: string): Promise<VehicleDashboard> {
    return firstValueFrom(
      this.http.get<VehicleDashboard>(`${this.baseUrl}/vehicle/${vehicleId}`),
    );
  }
}

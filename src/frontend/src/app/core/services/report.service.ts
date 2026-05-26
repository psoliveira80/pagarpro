import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ReportColumn {
  key: string;
  label: string;
  format: string;
}

export interface ReportRow {
  values: Record<string, string>;
}

export interface ReportResponse {
  columns: ReportColumn[];
  rows: ReportRow[];
  total: number;
}

export interface ReportDefinition {
  slug: string;
  name: string;
  description: string;
  icon: string;
}

export interface CustomReportRequest {
  dimensions: string[];
  measures: string[];
  filters?: {
    date_from?: string;
    date_to?: string;
    customer_id?: string;
    status?: string;
  };
  limit?: number;
}

export interface SavedReport {
  id: string;
  name: string;
  description: string | null;
  is_shared: boolean;
  definition: Record<string, unknown>;
  criado_em: string;
}

@Injectable({ providedIn: 'root' })
export class ReportService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/reports`;

  readonly builtInReports: ReportDefinition[] = [
    {
      slug: 'receivables',
      name: 'Recebíveis Detalhado',
      description: 'Relatório completo de parcelas com filtros por período, status e cliente',
      icon: 'heroCurrencyDollar',
    },
    {
      slug: 'customers',
      name: 'Clientes por Receita',
      description: 'Ranking de clientes por receita total, score e inadimplência',
      icon: 'heroUsers',
    },
    {
      slug: 'vehicles',
      name: 'Veículos por ROI',
      description: 'Análise de retorno por veículo com FIPE, receita e despesas',
      icon: 'heroTruck',
    },
    {
      slug: 'dre',
      name: 'DRE Consolidado',
      description: 'Demonstrativo de Resultado do Exercício por período',
      icon: 'heroChartBarSquare',
    },
  ];

  async getReport(
    slug: string,
    params?: {
      date_from?: string;
      date_to?: string;
      status?: string;
      customer_id?: string;
      export?: string;
    },
  ): Promise<ReportResponse> {
    let httpParams = new HttpParams();
    if (params?.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params?.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params?.status) httpParams = httpParams.set('status', params.status);
    if (params?.customer_id)
      httpParams = httpParams.set('customer_id', params.customer_id);
    if (params?.export) httpParams = httpParams.set('export', params.export);

    return firstValueFrom(
      this.http.get<ReportResponse>(`${this.baseUrl}/${slug}`, {
        params: httpParams,
      }),
    );
  }

  async exportCsv(slug: string, params?: Record<string, string>): Promise<Blob> {
    let httpParams = new HttpParams().set('export', 'csv');
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v) httpParams = httpParams.set(k, v);
      }
    }
    return firstValueFrom(
      this.http.get(`${this.baseUrl}/${slug}`, {
        params: httpParams,
        responseType: 'blob',
      }),
    );
  }

  async runCustomReport(request: CustomReportRequest): Promise<ReportResponse> {
    return firstValueFrom(
      this.http.post<ReportResponse>(`${this.baseUrl}/custom`, request),
    );
  }

  async saveReport(payload: {
    name: string;
    description?: string;
    is_shared?: boolean;
    definition: Record<string, unknown>;
  }): Promise<SavedReport> {
    return firstValueFrom(
      this.http.post<SavedReport>(`${this.baseUrl}/saved`, payload),
    );
  }

  async listSavedReports(): Promise<SavedReport[]> {
    return firstValueFrom(
      this.http.get<SavedReport[]>(`${this.baseUrl}/saved`),
    );
  }
}

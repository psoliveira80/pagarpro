import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// --- Integrations ---
export interface Integration {
  id: string;
  category: string;
  provider: string;
  is_active: boolean;
  config: Record<string, unknown>;
  status: string;
  last_health_check: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationCreate {
  category: string;
  provider: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface IntegrationUpdate {
  provider?: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface IntegrationTestResult {
  integration_id: string;
  status: string;
  latency_ms: number | null;
  error: string | null;
}

// --- Audit Log ---
export interface AuditLogEntry {
  id: number;
  user_id: string | null;
  action: string;
  entity: string | null;
  entity_id: string | null;
  payload_before: Record<string, unknown> | null;
  payload_after: Record<string, unknown> | null;
  ip: string | null;
  user_agent: string | null;
  correlation_id: string | null;
  module: string | null;
  category: string;
  severity: string;
  hmac_valid: boolean;
  criado_em: string;
}

export interface AuditLogSearchResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  size: number;
}

// --- Modules ---
export interface AppModule {
  module_id: string;
  is_active: boolean;
  config: Record<string, unknown> | null;
  registered_at: string;
}

export interface ModuleHook {
  id: string;
  module_id: string;
  event_type: string;
  policy: Record<string, unknown> | null;
  is_active: boolean;
}

// --- Settings ---
export interface SystemSetting {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
}

// --- Backup ---
export interface Backup {
  name: string;
  size: number | null;
  created_at: string | null;
}

// --- Metrics ---
export interface SystemMetrics {
  db_pool_size: number;
  db_pool_checked_out: number;
  redis_connected_clients: number;
  redis_used_memory_mb: number;
  celery_active_tasks: number;
  celery_reserved_tasks: number;
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/admin`;

  // ─── Integrations ───

  async listIntegrations(): Promise<Integration[]> {
    return firstValueFrom(this.http.get<Integration[]>(`${this.baseUrl}/integrations`));
  }

  async createIntegration(payload: IntegrationCreate): Promise<Integration> {
    return firstValueFrom(
      this.http.post<Integration>(`${this.baseUrl}/integrations`, payload),
    );
  }

  async updateIntegration(id: string, payload: IntegrationUpdate): Promise<Integration> {
    return firstValueFrom(
      this.http.put<Integration>(`${this.baseUrl}/integrations/${id}`, payload),
    );
  }

  async deleteIntegration(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.baseUrl}/integrations/${id}`));
  }

  async testIntegration(id: string): Promise<IntegrationTestResult> {
    return firstValueFrom(
      this.http.post<IntegrationTestResult>(`${this.baseUrl}/integrations/${id}/test`, {}),
    );
  }

  // ─── Audit Log ───

  async searchAuditLog(params: {
    action?: string;
    user_id?: string;
    entity?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    size?: number;
  }): Promise<AuditLogSearchResponse> {
    let httpParams = new HttpParams();
    if (params.action) httpParams = httpParams.set('action', params.action);
    if (params.user_id) httpParams = httpParams.set('user_id', params.user_id);
    if (params.entity) httpParams = httpParams.set('entity', params.entity);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<AuditLogSearchResponse>(`${this.baseUrl}/audit-log`, { params: httpParams }),
    );
  }

  // ─── Modules ───

  async listModules(): Promise<AppModule[]> {
    return firstValueFrom(this.http.get<AppModule[]>(`${this.baseUrl}/modules`));
  }

  async updateModule(moduleId: string, payload: { is_active?: boolean; config?: Record<string, unknown> }): Promise<AppModule> {
    return firstValueFrom(
      this.http.put<AppModule>(`${this.baseUrl}/modules/${moduleId}`, payload),
    );
  }

  async listModuleHooks(moduleId: string): Promise<ModuleHook[]> {
    return firstValueFrom(
      this.http.get<ModuleHook[]>(`${this.baseUrl}/modules/${moduleId}/hooks`),
    );
  }

  // ─── Settings ───

  async getSettings(): Promise<SystemSetting[]> {
    return firstValueFrom(this.http.get<SystemSetting[]>(`${this.baseUrl}/settings`));
  }

  async updateSettings(settings: Record<string, Record<string, unknown>>): Promise<SystemSetting[]> {
    return firstValueFrom(
      this.http.put<SystemSetting[]>(`${this.baseUrl}/settings`, { settings }),
    );
  }

  // ─── Backup ───

  async triggerBackup(): Promise<{ task_id: string; message: string }> {
    return firstValueFrom(
      this.http.post<{ task_id: string; message: string }>(`${this.baseUrl}/backup`, {}),
    );
  }

  async listBackups(): Promise<Backup[]> {
    return firstValueFrom(this.http.get<Backup[]>(`${this.baseUrl}/backups`));
  }

  // ─── Metrics ───

  async getMetrics(): Promise<SystemMetrics> {
    return firstValueFrom(this.http.get<SystemMetrics>(`${this.baseUrl}/metrics`));
  }
}

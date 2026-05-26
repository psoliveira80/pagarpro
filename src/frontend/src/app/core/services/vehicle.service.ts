import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — PT-BR puro alinhado com Pydantic (12-3c).

export interface Aquisicao {
  id: string;
  veiculo_id: string;
  tipo_aquisicao: string;
  preco_compra: number | null;
  data_compra: string | null;
  banco_financiamento: string | null;
  contrato_financiamento: string | null;
  parcelas_financiamento: number | null;
  valor_mensal_financiamento: number | null;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface Veiculo {
  id: string;
  placa: string;
  marca: string;
  modelo: string;
  ano_modelo: number;
  ano_fabricacao: number;
  cor: string | null;
  chassi: string | null;
  renavam: string | null;
  codigo_fipe: string | null;
  valor_fipe: number | null;
  status: string;
  cliente_id: string | null;
  asset_id: string | null;
  rastreador_id: string | null;
  metadados: Record<string, unknown> | null;
  aquisicao: Aquisicao | null;
  criado_em: string;
  atualizado_em: string;
}

export interface VeiculoListResponse {
  items: Veiculo[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface AquisicaoCreatePayload {
  tipo_aquisicao?: string;
  preco_compra?: number;
  data_compra?: string;
  banco_financiamento?: string;
  contrato_financiamento?: string;
  parcelas_financiamento?: number;
  valor_mensal_financiamento?: number;
  observacoes?: string;
}

export interface VeiculoCreatePayload {
  placa: string;
  marca: string;
  modelo: string;
  ano_modelo: number;
  ano_fabricacao: number;
  cor?: string;
  chassi?: string;
  renavam?: string;
  codigo_fipe?: string;
  valor_fipe?: number;
  status?: string;
  cliente_id?: string;
  rastreador_id?: string;
  metadados?: Record<string, unknown>;
  aquisicao?: AquisicaoCreatePayload;
}

export interface FipeMarca {
  codigo: string;
  nome: string;
}

export interface FipeModelo {
  codigo: string;
  nome: string;
}

export interface FipeAno {
  codigo: string;
  nome: string;
}

export interface FipePreco {
  preco: string;
  marca: string;
  modelo: string;
  ano_modelo: number;
  combustivel: string;
  codigo_fipe: string;
  mes_referencia: string;
  tipo_veiculo: number;
}

export interface VeiculoFinanceiro {
  veiculo_id: string;
  valor_fipe: number | null;
  aquisicao: Aquisicao | null;
}

export interface BloqueioDesbloqueioPayload {
  senha: string;
  motivo?: string;
}

@Injectable({ providedIn: 'root' })
export class VehicleService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiBaseUrl}/vehicles`;

  async list(params: {
    search?: string;
    status?: string;
    customer_id?: string;
    page?: number;
    size?: number;
  }): Promise<VeiculoListResponse> {
    let httpParams = new HttpParams();
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.status && params.status !== 'todos')
      httpParams = httpParams.set('status', params.status);
    if (params.customer_id) httpParams = httpParams.set('customer_id', params.customer_id);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<VeiculoListResponse>(this.apiUrl, { params: httpParams }),
    );
  }

  async getById(id: string): Promise<Veiculo> {
    return firstValueFrom(this.http.get<Veiculo>(`${this.apiUrl}/${id}`));
  }

  async create(payload: VeiculoCreatePayload): Promise<Veiculo> {
    return firstValueFrom(this.http.post<Veiculo>(this.apiUrl, payload));
  }

  async update(id: string, payload: Partial<VeiculoCreatePayload>): Promise<Veiculo> {
    return firstValueFrom(this.http.patch<Veiculo>(`${this.apiUrl}/${id}`, payload));
  }

  async delete(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.apiUrl}/${id}`));
  }

  async getFinancials(id: string): Promise<VeiculoFinanceiro> {
    return firstValueFrom(
      this.http.get<VeiculoFinanceiro>(`${this.apiUrl}/${id}/financials`),
    );
  }

  async block(id: string, payload: BloqueioDesbloqueioPayload): Promise<{ status: string; vehicle_id: string }> {
    return firstValueFrom(
      this.http.post<{ status: string; vehicle_id: string }>(`${this.apiUrl}/${id}/block`, payload),
    );
  }

  async unblock(id: string, payload: BloqueioDesbloqueioPayload): Promise<{ status: string; vehicle_id: string }> {
    return firstValueFrom(
      this.http.post<{ status: string; vehicle_id: string }>(`${this.apiUrl}/${id}/unblock`, payload),
    );
  }

  async getFipeBrands(vehicleType = 'carros'): Promise<FipeMarca[]> {
    const params = new HttpParams().set('vehicle_type', vehicleType);
    return firstValueFrom(this.http.get<FipeMarca[]>(`${this.apiUrl}/fipe/brands`, { params }));
  }

  async getFipeModels(brandCode: string, vehicleType = 'carros'): Promise<FipeModelo[]> {
    const params = new HttpParams().set('vehicle_type', vehicleType);
    return firstValueFrom(
      this.http.get<FipeModelo[]>(`${this.apiUrl}/fipe/brands/${brandCode}/models`, { params }),
    );
  }

  async getFipeYears(brandCode: string, modelCode: string, vehicleType = 'carros'): Promise<FipeAno[]> {
    const params = new HttpParams().set('vehicle_type', vehicleType);
    return firstValueFrom(
      this.http.get<FipeAno[]>(
        `${this.apiUrl}/fipe/brands/${brandCode}/models/${modelCode}/years`,
        { params },
      ),
    );
  }

  async getFipePrice(
    brandCode: string,
    modelCode: string,
    yearCode: string,
    vehicleType = 'carros',
  ): Promise<FipePreco> {
    const params = new HttpParams().set('vehicle_type', vehicleType);
    return firstValueFrom(
      this.http.get<FipePreco>(
        `${this.apiUrl}/fipe/brands/${brandCode}/models/${modelCode}/years/${yearCode}/price`,
        { params },
      ),
    );
  }
}

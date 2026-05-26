import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — PT-BR puro alinhado com Pydantic (12-3c).

export interface CategoriaDespesa {
  id: string;
  nome: string;
  categoria_pai_id: string | null;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

export interface Fornecedor {
  id: string;
  nome: string;
  cpf_cnpj: string | null;
  contato: string | null;
  email: string | null;
  observacoes: string | null;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

export interface TituloPagar {
  id: string;
  fornecedor_id: string | null;
  categoria_id: string | null;
  descricao: string;
  valor: number;
  data_vencimento: string;
  data_pagamento: string | null;
  forma_pagamento: string | null;
  status: 'rascunho' | 'pendente' | 'pago' | 'vencido' | 'cancelado';
  titulo_receber_origem_id: string | null;
  observacoes: string | null;
  comprovante_url: string | null;
  template_id: string | null;
  criado_por_id: string;
  criado_em: string;
  atualizado_em: string;
}

export interface TituloPagarListResponse {
  items: TituloPagar[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface TituloPagarCreatePayload {
  fornecedor_id?: string;
  categoria_id?: string;
  descricao: string;
  valor: number;
  data_vencimento: string;
  observacoes?: string;
}

export interface DespesaRecorrente {
  id: string;
  fornecedor_id: string | null;
  categoria_id: string | null;
  descricao: string;
  valor: number;
  periodicidade: 'mensal' | 'semanal' | 'quinzenal';
  dia_do_mes: number | null;
  ativo: boolean;
  proxima_geracao_em: string;
  criado_por_id: string;
  criado_em: string;
  atualizado_em: string;
}

export interface DespesaRecorrenteCreatePayload {
  fornecedor_id?: string;
  categoria_id?: string;
  descricao: string;
  valor: number;
  periodicidade: string;
  dia_do_mes?: number;
  proxima_geracao_em: string;
  ativo?: boolean;
}

export interface PagamentoRapidoPayload {
  fornecedor_id?: string;
  categoria_id?: string;
  descricao: string;
  valor: number;
  data_vencimento: string;
  data_pagamento: string;
  forma_pagamento: string;
  observacoes?: string;
}

export interface DreDetalhamentoCategoria {
  categoria_id: string | null;
  categoria_nome: string | null;
  total: number;
}

export interface DreSecao {
  total: number;
  por_categoria: DreDetalhamentoCategoria[];
}

export interface DreResponse {
  periodo_inicio: string;
  periodo_fim: string;
  receitas: DreSecao;
  despesas: DreSecao;
  resultado_liquido: number;
}

export interface FornecedorListResponse {
  items: Fornecedor[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

@Injectable({ providedIn: 'root' })
export class PayableService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  // --- Categorias de Despesa ---
  async listCategories(): Promise<CategoriaDespesa[]> {
    return firstValueFrom(
      this.http.get<CategoriaDespesa[]>(`${this.baseUrl}/categorias-despesa`),
    );
  }

  async createCategory(payload: { nome: string; categoria_pai_id?: string }): Promise<CategoriaDespesa> {
    return firstValueFrom(
      this.http.post<CategoriaDespesa>(`${this.baseUrl}/categorias-despesa`, payload),
    );
  }

  // --- Fornecedores ---
  async listSuppliers(params?: {
    search?: string;
    page?: number;
    size?: number;
  }): Promise<FornecedorListResponse> {
    let httpParams = new HttpParams();
    if (params?.search) httpParams = httpParams.set('search', params.search);
    if (params?.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params?.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<FornecedorListResponse>(`${this.baseUrl}/fornecedores`, { params: httpParams }),
    );
  }

  async createSupplier(payload: Partial<Fornecedor>): Promise<Fornecedor> {
    return firstValueFrom(
      this.http.post<Fornecedor>(`${this.baseUrl}/fornecedores`, payload),
    );
  }

  // --- Títulos a Pagar ---
  async listPayables(params: {
    search?: string;
    status?: string;
    fornecedor_id?: string;
    categoria_id?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    size?: number;
  }): Promise<TituloPagarListResponse> {
    let httpParams = new HttpParams();
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.status && params.status !== 'todos')
      httpParams = httpParams.set('status', params.status);
    if (params.fornecedor_id) httpParams = httpParams.set('fornecedor_id', params.fornecedor_id);
    if (params.categoria_id) httpParams = httpParams.set('categoria_id', params.categoria_id);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<TituloPagarListResponse>(`${this.baseUrl}/titulos-pagar`, { params: httpParams }),
    );
  }

  async createPayable(payload: TituloPagarCreatePayload): Promise<TituloPagar> {
    return firstValueFrom(
      this.http.post<TituloPagar>(`${this.baseUrl}/titulos-pagar`, payload),
    );
  }

  async updatePayable(id: string, payload: Partial<TituloPagarCreatePayload>): Promise<TituloPagar> {
    return firstValueFrom(
      this.http.patch<TituloPagar>(`${this.baseUrl}/titulos-pagar/${id}`, payload),
    );
  }

  async deletePayable(id: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.baseUrl}/titulos-pagar/${id}`),
    );
  }

  async payPayable(id: string, payload: { forma_pagamento: string; data_pagamento: string }): Promise<TituloPagar> {
    return firstValueFrom(
      this.http.post<TituloPagar>(`${this.baseUrl}/titulos-pagar/${id}/pay`, payload),
    );
  }

  async quickPay(payload: PagamentoRapidoPayload): Promise<TituloPagar> {
    return firstValueFrom(
      this.http.post<TituloPagar>(`${this.baseUrl}/titulos-pagar/quick-pay`, payload),
    );
  }

  // --- Despesas Recorrentes ---
  async listRecurring(): Promise<DespesaRecorrente[]> {
    return firstValueFrom(
      this.http.get<DespesaRecorrente[]>(`${this.baseUrl}/despesas-recorrentes`),
    );
  }

  async createRecurring(payload: DespesaRecorrenteCreatePayload): Promise<DespesaRecorrente> {
    return firstValueFrom(
      this.http.post<DespesaRecorrente>(`${this.baseUrl}/despesas-recorrentes`, payload),
    );
  }

  async updateRecurring(
    id: string,
    payload: Partial<DespesaRecorrenteCreatePayload>,
  ): Promise<DespesaRecorrente> {
    return firstValueFrom(
      this.http.patch<DespesaRecorrente>(`${this.baseUrl}/despesas-recorrentes/${id}`, payload),
    );
  }

  async deleteRecurring(id: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.baseUrl}/despesas-recorrentes/${id}`),
    );
  }

  // --- DRE Report ---
  async getDreReport(params: {
    period_start: string;
    period_end: string;
  }): Promise<DreResponse> {
    const httpParams = new HttpParams()
      .set('period_start', params.period_start)
      .set('period_end', params.period_end);

    return firstValueFrom(
      this.http.get<DreResponse>(`${this.baseUrl}/reports/dre`, { params: httpParams }),
    );
  }
}

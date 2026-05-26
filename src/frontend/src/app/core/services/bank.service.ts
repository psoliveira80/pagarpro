import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — PT-BR puro alinhado com Pydantic (12-3c).

export interface ContaBancaria {
  id: string;
  nome: string;
  codigo_banco: string | null;
  nome_banco: string | null;
  agencia: string | null;
  numero_conta: string | null;
  tipo: string;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
}

export interface ContaBancariaCreatePayload {
  nome: string;
  codigo_banco?: string;
  nome_banco?: string;
  agencia?: string;
  numero_conta?: string;
  tipo?: string;
}

export interface TransacaoBancaria {
  id: string;
  conta_id: string;
  fitid: string;
  lancado_em: string;
  valor: number;
  descricao_bruta: string | null;
  descricao_limpa: string | null;
  tipo: string | null;
  status: 'pendente' | 'conciliada' | 'ignorada';
  conciliado_com_tipo: string | null;
  conciliado_com_id: string | null;
  importado_de: string;
  importado_em: string;
}

export interface TransacaoBancariaListResponse {
  items: TransacaoBancaria[];
  total: number;
  page: number;
  size: number;
}

export interface ResumoImportacao {
  total_parseado: number;
  novos_inseridos: number;
  duplicatas_puladas: number;
}

export interface SugestaoConciliacao {
  transacao_id: string;
  tipo_destino: string;
  destino_id: string;
  pontuacao: number;
  diferenca_valor: number;
  diferenca_dias: number;
  similaridade_descricao: number;
}

export interface AutoConciliacaoResponse {
  sugestoes: SugestaoConciliacao[];
}

export interface ConciliarRequest {
  transacao_ids: string[];
  tipo_destino: string;
  destino_id: string;
}

export interface ConfirmarConciliacaoResponse {
  quantidade_conciliada: number;
}

export interface DivergenciaItem {
  categoria: string;
  tipo_entidade: string;
  entidade_id: string;
  descricao: string;
  valor: number | null;
  lancado_em: string | null;
  detalhes: string | null;
}

export interface DivergenciasResponse {
  transacoes_orfas: DivergenciaItem[];
  titulos_suspeitos_pagos: DivergenciaItem[];
  divergencias_valor: DivergenciaItem[];
  total_orfas: number;
  total_suspeitos: number;
  total_divergencias: number;
}

export interface LinhaPdfParseada {
  fitid: string;
  lancado_em: string;
  valor: number;
  descricao_bruta: string;
  descricao_limpa: string;
  tipo: string;
  selecionada: boolean;
}

export interface PdfParseResponse {
  linhas: LinhaPdfParseada[];
  confianca: number;
  total_linhas: number;
}

@Injectable({ providedIn: 'root' })
export class BankService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  // --- Contas Bancárias ---
  async listAccounts(activeOnly = true): Promise<ContaBancaria[]> {
    const params = new HttpParams().set('active_only', activeOnly.toString());
    return firstValueFrom(
      this.http.get<ContaBancaria[]>(`${this.baseUrl}/contas-bancarias`, { params }),
    );
  }

  async createAccount(payload: ContaBancariaCreatePayload): Promise<ContaBancaria> {
    return firstValueFrom(
      this.http.post<ContaBancaria>(`${this.baseUrl}/contas-bancarias`, payload),
    );
  }

  async updateAccount(id: string, payload: Partial<ContaBancariaCreatePayload>): Promise<ContaBancaria> {
    return firstValueFrom(
      this.http.patch<ContaBancaria>(`${this.baseUrl}/contas-bancarias/${id}`, payload),
    );
  }

  async deleteAccount(id: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.baseUrl}/contas-bancarias/${id}`),
    );
  }

  // --- OFX Import ---
  async importOfx(accountId: string, file: File): Promise<ResumoImportacao> {
    const formData = new FormData();
    formData.append('file', file);
    return firstValueFrom(
      this.http.post<ResumoImportacao>(
        `${this.baseUrl}/conciliacao/import-ofx/${accountId}`,
        formData,
      ),
    );
  }

  // --- PDF Import ---
  async importPdfParse(accountId: string, file: File): Promise<PdfParseResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return firstValueFrom(
      this.http.post<PdfParseResponse>(
        `${this.baseUrl}/conciliacao/import-pdf/${accountId}`,
        formData,
      ),
    );
  }

  async importPdfConfirm(accountId: string, linhas: LinhaPdfParseada[]): Promise<ResumoImportacao> {
    return firstValueFrom(
      this.http.post<ResumoImportacao>(
        `${this.baseUrl}/conciliacao/import-pdf/confirm`,
        { conta_id: accountId, linhas },
      ),
    );
  }

  // --- Transactions ---
  async listTransactions(params: {
    conta_id?: string;
    status?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    size?: number;
  }): Promise<TransacaoBancariaListResponse> {
    let httpParams = new HttpParams();
    if (params.conta_id) httpParams = httpParams.set('conta_id', params.conta_id);
    if (params.status) httpParams = httpParams.set('status', params.status);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<TransacaoBancariaListResponse>(
        `${this.baseUrl}/conciliacao/transactions`,
        { params: httpParams },
      ),
    );
  }

  // --- Conciliação ---
  async confirmMatch(request: ConciliarRequest): Promise<ConfirmarConciliacaoResponse> {
    return firstValueFrom(
      this.http.post<ConfirmarConciliacaoResponse>(
        `${this.baseUrl}/conciliacao/match`,
        request,
      ),
    );
  }

  async ignoreTransaction(txId: string): Promise<void> {
    await firstValueFrom(
      this.http.post<unknown>(
        `${this.baseUrl}/conciliacao/transactions/${txId}/ignore`,
        {},
      ),
    );
  }

  // --- Auto-match suggestions ---
  async getMatchSuggestions(accountId?: string): Promise<AutoConciliacaoResponse> {
    let params = new HttpParams();
    if (accountId) params = params.set('account_id', accountId);
    return firstValueFrom(
      this.http.get<AutoConciliacaoResponse>(
        `${this.baseUrl}/conciliacao/match-suggestions`,
        { params },
      ),
    );
  }

  // --- Divergências ---
  async getDivergences(tolerance?: number): Promise<DivergenciasResponse> {
    let params = new HttpParams();
    if (tolerance !== undefined) params = params.set('tolerance', tolerance.toString());
    return firstValueFrom(
      this.http.get<DivergenciasResponse>(
        `${this.baseUrl}/conciliacao/divergences`,
        { params },
      ),
    );
  }
}

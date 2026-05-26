import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// Story 12-8 — PT-BR puro, alinhado com Pydantic (12-3c).

export interface Contrato {
  id: string;
  cliente_id: string;
  veiculo_id: string | null;
  numero: string;
  status: 'rascunho' | 'vigente' | 'suspenso' | 'encerrado' | 'rescindido' | 'cancelado';
  data_inicio: string;
  data_fim: string;
  valor_total: number;
  observacoes: string | null;
  pdf_url: string | null;
  versao_pdf: number;
  clausulas_md: string | null;
  termos: Record<string, unknown> | null;
  criado_por_id: string | null;
  criado_em: string;
  atualizado_em: string;
  titulos: TituloReceberContrato[];
}

export interface ContratoListResponse {
  items: Contrato[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface TituloReceberContrato {
  id: string;
  contrato_id: string;
  lote_id: string | null;
  titulo_origem_id: string | null;
  sequencia: number;
  data_vencimento: string;
  valor: number;
  valor_pago: number;
  status: string;
  pago_em: string | null;
  forma_pagamento: string | null;
  comprovante_url: string | null;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface EventoContrato {
  id: string;
  contrato_id: string;
  tipo: string;
  descricao: string;
  payload: Record<string, unknown> | null;
  criado_por_id: string | null;
  criado_em: string;
}

export interface LoteGeracao {
  id: string;
  contrato_id: string;
  numero_geracao: number;
  gerado_em: string;
  gerado_por_id: string | null;
  config: Record<string, unknown>;
  status: string;
}

export interface PreviewTitulo {
  sequencia: number;
  data_vencimento: string;
  principal: number;
  juros: number;
  valor: number;
}

export interface PreviewPlanilhaParams {
  valor_total: number;
  quantidade_parcelas: number;
  data_inicio: string;
  periodicidade?: string;
  taxa_juros?: number;
  metodo?: string;
  datas_customizadas?: string[];
}

export interface PreviewPlanilhaResponse {
  titulos: PreviewTitulo[];
  total: number;
  total_juros: number;
}

export interface SimulacaoParams {
  valor_total: number;
  quantidade_parcelas: number;
  data_inicio: string;
  periodicidade?: string;
  taxa_juros?: number;
  metodo?: string;
}

export interface ResumoSimulacao {
  total_pago: number;
  total_juros: number;
  total_principal: number;
  taxa_efetiva: number;
}

export interface SimulacaoResponse {
  titulos: PreviewTitulo[];
  resumo: ResumoSimulacao;
}

export interface ContratoCreatePayload {
  cliente_id: string;
  veiculo_id?: string | null;
  numero: string;
  data_inicio: string;
  data_fim: string;
  valor_total: number;
  observacoes?: string;
  clausulas_md?: string;
  termos?: Record<string, unknown>;
  quantidade_parcelas: number;
  periodicidade?: string;
  taxa_juros?: number;
  metodo?: string;
  datas_customizadas?: string[];
}

export interface ContratoUpdatePayload {
  cliente_id?: string;
  veiculo_id?: string | null;
  numero?: string;
  data_inicio?: string;
  data_fim?: string;
  valor_total?: number;
  observacoes?: string;
  clausulas_md?: string;
}

export interface EdicaoLoteAcao {
  titulo_id: string;
  acao: 'postpone' | 'discount' | 'set_value' | 'cancel';
  params?: Record<string, unknown>;
}

export interface EdicaoLotePayload {
  acoes: EdicaoLoteAcao[];
  dry_run?: boolean;
}

export interface EdicaoLoteDiff {
  titulo_id: string;
  acao: string;
  valor_antigo: number;
  valor_novo: number;
  data_vencimento_antiga: string | null;
  data_vencimento_nova: string | null;
}

export interface EdicaoLoteResponse {
  aplicado: boolean;
  diffs: EdicaoLoteDiff[];
}

export interface RescindirContratoPayload {
  motivo: string;
  data_efetiva: string;
  valor_multa?: number;
}

export interface ResumoRescisao {
  contrato_id: string;
  quantidade_titulos_em_aberto: number;
  total_titulos_em_aberto: number;
  total_pago: number;
  valor_multa: number;
  saldo_final: number;
  status: string;
}

@Injectable({ providedIn: 'root' })
export class ContractService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiBaseUrl}/contracts`;

  async list(params: {
    search?: string;
    status?: string;
    customer_id?: string;
    page?: number;
    size?: number;
  }): Promise<ContratoListResponse> {
    let httpParams = new HttpParams();
    if (params.search) httpParams = httpParams.set('search', params.search);
    if (params.status && params.status !== 'todos')
      httpParams = httpParams.set('status', params.status);
    if (params.customer_id) httpParams = httpParams.set('customer_id', params.customer_id);
    if (params.page !== undefined) httpParams = httpParams.set('page', params.page.toString());
    if (params.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return firstValueFrom(
      this.http.get<ContratoListResponse>(this.apiUrl, { params: httpParams }),
    );
  }

  async getById(id: string): Promise<Contrato> {
    return firstValueFrom(this.http.get<Contrato>(`${this.apiUrl}/${id}`));
  }

  async create(payload: ContratoCreatePayload): Promise<Contrato> {
    return firstValueFrom(this.http.post<Contrato>(this.apiUrl, payload));
  }

  async update(id: string, payload: ContratoUpdatePayload): Promise<Contrato> {
    return firstValueFrom(this.http.patch<Contrato>(`${this.apiUrl}/${id}`, payload));
  }

  async activate(id: string): Promise<{ id: string; status: string; mensagem: string }> {
    return firstValueFrom(
      this.http.post<{ id: string; status: string; mensagem: string }>(
        `${this.apiUrl}/${id}/activate`,
        {},
      ),
    );
  }

  async terminate(id: string, payload: RescindirContratoPayload): Promise<ResumoRescisao> {
    return firstValueFrom(
      this.http.post<ResumoRescisao>(`${this.apiUrl}/${id}/terminate`, payload),
    );
  }

  async previewSchedule(payload: PreviewPlanilhaParams): Promise<PreviewPlanilhaResponse> {
    return firstValueFrom(
      this.http.post<PreviewPlanilhaResponse>(`${this.apiUrl}/preview-schedule`, payload),
    );
  }

  async simulate(params: SimulacaoParams): Promise<SimulacaoResponse> {
    return firstValueFrom(
      this.http.post<SimulacaoResponse>(`${this.apiUrl}/simulate`, params),
    );
  }

  async bulkEditInstallments(contractId: string, payload: EdicaoLotePayload): Promise<EdicaoLoteResponse> {
    return firstValueFrom(
      this.http.post<EdicaoLoteResponse>(
        `${this.apiUrl}/${contractId}/installments/bulk-edit`,
        payload,
      ),
    );
  }

  async getEvents(contractId: string): Promise<{ items: EventoContrato[]; total: number; page: number; size: number; pages: number }> {
    return firstValueFrom(
      this.http.get<{ items: EventoContrato[]; total: number; page: number; size: number; pages: number }>(
        `${this.apiUrl}/${contractId}/events`,
      ),
    );
  }

  async getPdf(contractId: string): Promise<Blob> {
    return firstValueFrom(
      this.http.get(`${this.apiUrl}/${contractId}/pdf`, { responseType: 'blob' }),
    );
  }

  async getGenerations(contractId: string): Promise<LoteGeracao[]> {
    return firstValueFrom(
      this.http.get<LoteGeracao[]>(`${this.apiUrl}/${contractId}/generations`),
    );
  }

  async rollbackGeneration(contractId: string, generationId: string): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(
        `${this.apiUrl}/${contractId}/generations/${generationId}/rollback`,
        {},
      ),
    );
  }
}

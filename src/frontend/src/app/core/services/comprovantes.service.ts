import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export type StatusComprovante = 'analisado' | 'homologado' | 'rejeitado' | 'erro_analise';
export type MetodoAnalise = 'br_code' | 'pdf_texto' | 'ocr' | 'ia';

export interface Comprovante {
  id: string;
  titulo_id: string | null;
  cliente_id: string | null;
  arquivo_url: string;
  tipo_arquivo: string;
  metodo_analise: MetodoAnalise | null;
  score_confianca: number;
  valor_detectado: number | null;
  data_detectada: string | null;
  pix_e2e_id: string | null;
  pix_txid: string | null;
  banco_emissor: string | null;
  beneficiario_nome: string | null;
  beneficiario_cnpj: string | null;
  pagador_nome: string | null;
  pagador_documento: string | null;
  chave_pix_usada: string | null;
  avisos: string[];
  status: StatusComprovante;
  origem: string;
  criado_em: string;
  homologado_em: string | null;
  rejeitado_em: string | null;
  motivo_rejeicao: string | null;
}

export interface ListagemComprovantes {
  items: Comprovante[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface HomologarResponse {
  comprovante: Comprovante;
  titulo_atualizado: Record<string, unknown>;
}

@Injectable({ providedIn: 'root' })
export class ComprovantesService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/comprovantes`;

  async analisar(
    arquivo: File,
    titulo_id?: string,
    cliente_id?: string,
  ): Promise<Comprovante> {
    const form = new FormData();
    form.append('arquivo', arquivo);
    if (titulo_id) form.append('titulo_id', titulo_id);
    if (cliente_id) form.append('cliente_id', cliente_id);
    return firstValueFrom(
      this.http.post<Comprovante>(`${this.baseUrl}/analisar`, form),
    );
  }

  async listar(filtros?: {
    status?: StatusComprovante;
    score_minimo?: number;
    page?: number;
    size?: number;
  }): Promise<ListagemComprovantes> {
    const params: Record<string, string> = {};
    if (filtros?.status) params['status'] = filtros.status;
    if (filtros?.score_minimo !== undefined)
      params['score_minimo'] = String(filtros.score_minimo);
    if (filtros?.page) params['page'] = String(filtros.page);
    if (filtros?.size) params['size'] = String(filtros.size);
    return firstValueFrom(
      this.http.get<ListagemComprovantes>(this.baseUrl, { params }),
    );
  }

  async detalhar(id: string): Promise<Comprovante> {
    return firstValueFrom(this.http.get<Comprovante>(`${this.baseUrl}/${id}`));
  }

  async homologar(id: string): Promise<HomologarResponse> {
    return firstValueFrom(
      this.http.post<HomologarResponse>(`${this.baseUrl}/${id}/homologar`, {}),
    );
  }

  async rejeitar(id: string, motivo: string): Promise<Comprovante> {
    return firstValueFrom(
      this.http.post<Comprovante>(`${this.baseUrl}/${id}/rejeitar`, { motivo }),
    );
  }
}

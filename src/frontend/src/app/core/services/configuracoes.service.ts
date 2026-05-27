import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ConfiguracaoSistema {
  id: string;
  modulo: string;
  slug: string;
  tipo_valor: 'string' | 'inteiro' | 'decimal' | 'booleano' | 'json';
  valor: string;
  descricao: string | null;
  escopo: 'global' | 'tenant';
}

export interface ConfiguracaoUpdate {
  valor: string | number | boolean | Record<string, unknown>;
  tipo_valor: ConfiguracaoSistema['tipo_valor'];
  modulo?: string;
  descricao?: string;
}

@Injectable({ providedIn: 'root' })
export class ConfiguracoesService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/configuracoes`;

  async listar(modulo?: string): Promise<ConfiguracaoSistema[]> {
    let params = new HttpParams();
    if (modulo) params = params.set('modulo', modulo);
    return firstValueFrom(
      this.http.get<ConfiguracaoSistema[]>(this.baseUrl, { params }),
    );
  }

  async atualizar(slug: string, payload: ConfiguracaoUpdate): Promise<ConfiguracaoSistema> {
    return firstValueFrom(
      this.http.put<ConfiguracaoSistema>(`${this.baseUrl}/${slug}`, payload),
    );
  }
}

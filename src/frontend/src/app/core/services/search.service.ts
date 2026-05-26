import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SearchResultItem {
  id: string;
  type: string;
  title: string;
  subtitle: string | null;
  url: string;
}

export interface GlobalSearchResponse {
  results: SearchResultItem[];
  total: number;
}

@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiBaseUrl}/search`;

  async globalSearch(q: string, type?: string): Promise<GlobalSearchResponse> {
    let params = new HttpParams().set('q', q);
    if (type) params = params.set('type', type);
    return firstValueFrom(
      this.http.get<GlobalSearchResponse>(`${this.apiUrl}/global`, { params }),
    );
  }
}

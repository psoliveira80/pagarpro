import { Injectable, inject, signal, DestroyRef, NgZone } from '@angular/core';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

export interface ServerEvent {
  type: string;
  [key: string]: unknown;
}

@Injectable({ providedIn: 'root' })
export class SseService {
  private readonly authService = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly zone = inject(NgZone);
  private eventSource: EventSource | null = null;

  readonly connected = signal(false);
  readonly lastEvent = signal<ServerEvent | null>(null);

  connect(): void {
    this.disconnect();

    const token = this.authService.getToken();
    if (!token) return;

    const baseUrl = environment.apiBaseUrl.replace('/api/v1', '');
    const url = `${baseUrl}/sse/notifications?token=${encodeURIComponent(token)}`;

    this.zone.runOutsideAngular(() => {
      this.eventSource = new EventSource(url);

      this.eventSource.onopen = () => {
        this.zone.run(() => this.connected.set(true));
      };

      this.eventSource.addEventListener('notification', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as ServerEvent;
          this.zone.run(() => this.lastEvent.set(data));
        } catch {
          // Ignore malformed events
        }
      });

      this.eventSource.onerror = () => {
        this.zone.run(() => this.connected.set(false));
      };
    });

    this.destroyRef.onDestroy(() => this.disconnect());
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.connected.set(false);
    }
  }
}

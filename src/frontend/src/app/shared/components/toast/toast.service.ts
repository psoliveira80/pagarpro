import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  duration: number;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private nextId = 0;

  readonly toasts = signal<Toast[]>([]);

  show(options: { message: string; type?: Toast['type']; duration?: number }): void {
    const toast: Toast = {
      id: this.nextId++,
      message: options.message,
      type: options.type ?? 'info',
      duration: options.duration ?? 4000,
    };

    this.toasts.update((list) => [...list, toast]);

    setTimeout(() => this.dismiss(toast.id), toast.duration);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }
}

import { Injectable } from '@angular/core';
import Swal from 'sweetalert2';

@Injectable({ providedIn: 'root' })
export class ConfirmService {
  async confirm(options: {
    title?: string;
    text: string;
    confirmText?: string;
    cancelText?: string;
    type?: 'warning' | 'danger' | 'info';
  }): Promise<boolean> {
    const colorMap = {
      warning: '#f59e0b',
      danger: '#ef4444',
      info: '#6366f1',
    };
    const color = colorMap[options.type ?? 'warning'];

    const result = await Swal.fire({
      title: options.title ?? 'Confirmar',
      text: options.text,
      icon: options.type === 'danger' ? 'warning' : 'question',
      showCancelButton: true,
      confirmButtonText: options.confirmText ?? 'Confirmar',
      cancelButtonText: options.cancelText ?? 'Cancelar',
      confirmButtonColor: color,
      cancelButtonColor: '#6b7280',
      background: 'var(--surface-elevated)',
      color: 'var(--text-primary)',
      customClass: {
        popup: 'rounded-2xl border border-[var(--border)]',
      },
    });

    return result.isConfirmed;
  }
}

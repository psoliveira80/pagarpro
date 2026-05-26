import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import {
  ReceivableService,
  TituloReceber,
} from '../../core/services/receivable.service';

@Component({
  selector: 'app-validation-queue',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './validation-queue.component.html',
  styleUrl: './validation-queue.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ValidationQueueComponent implements OnInit {
  private readonly receivableService = inject(ReceivableService);

  readonly items = signal<TituloReceber[]>([]);
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly selectedItem = signal<TituloReceber | null>(null);
  readonly processingId = signal<string | null>(null);

  ngOnInit(): void {
    this.loadQueue();
  }

  async loadQueue(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const data = await this.receivableService.getFilaValidacao();
      this.items.set(data.items);
    } catch {
      this.items.set([]);
      this.error.set('Erro ao carregar fila de validação. Verifique sua conexão.');
    } finally {
      this.isLoading.set(false);
    }
  }

  selectItem(item: TituloReceber): void {
    this.selectedItem.set(item);
  }

  async approve(item: TituloReceber): Promise<void> {
    this.processingId.set(item.id);
    try {
      await this.receivableService.validar(item.id, { aprovado: true });
      await this.loadQueue();
      this.selectedItem.set(null);
    } catch {
      // Error handled
    } finally {
      this.processingId.set(null);
    }
  }

  async reject(item: TituloReceber): Promise<void> {
    this.processingId.set(item.id);
    try {
      await this.receivableService.validar(item.id, {
        aprovado: false,
        observacoes: 'Rejeitado manualmente',
      });
      await this.loadQueue();
      this.selectedItem.set(null);
    } catch {
      // Error handled
    } finally {
      this.processingId.set(null);
    }
  }

  isProcessing(id: string): boolean {
    return this.processingId() === id;
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }

  formatDateTime(date: string): string {
    return new Date(date).toLocaleString('pt-BR');
  }
}

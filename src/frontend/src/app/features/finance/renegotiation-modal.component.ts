import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
  computed,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import {
  ReceivableService,
  TituloReceber,
} from '../../core/services/receivable.service';
import { ContractService } from '../../core/services/contract.service';

@Component({
  selector: 'app-renegotiation-modal',
  standalone: true,
  imports: [FormsModule, ModalComponent],
  templateUrl: './renegotiation-modal.component.html',
  styleUrl: './renegotiation-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RenegotiationModalComponent {
  private readonly receivableService = inject(ReceivableService);
  private readonly contractService = inject(ContractService);

  readonly open = input(true);
  readonly receivables = input.required<TituloReceber[]>();
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly startDate = signal('');
  readonly numInstallments = signal(3);
  readonly isSaving = signal(false);
  readonly isLoadingPreview = signal(false);
  readonly preview = signal<{ data_vencimento: string; valor: number }[]>([]);

  readonly totalOverdue = computed(() =>
    this.receivables().reduce((sum, r) => sum + r.valor, 0),
  );

  async loadPreview(): Promise<void> {
    if (!this.startDate() || this.numInstallments() < 1) return;
    this.isLoadingPreview.set(true);
    try {
      const result = await this.contractService.previewSchedule({
        valor_total: this.totalOverdue(),
        quantidade_parcelas: this.numInstallments(),
        data_inicio: this.startDate(),
        periodicidade: 'mensal',
        metodo: 'fixo',
      });
      this.preview.set(
        result.titulos.map((i: { data_vencimento: string; valor: number }) => ({
          data_vencimento: i.data_vencimento,
          valor: i.valor,
        })),
      );
    } catch {
      this.preview.set([]);
    } finally {
      this.isLoadingPreview.set(false);
    }
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      await this.receivableService.renegociar({
        titulos_ids: this.receivables().map((r) => r.id),
        nova_planilha: {
          valor_total: this.totalOverdue(),
          quantidade_parcelas: this.numInstallments(),
          data_inicio: this.startDate(),
          periodicidade: 'mensal',
          metodo: 'fixo',
        },
      });
      this.saved.emit();
    } catch {
      // Error handled
    } finally {
      this.isSaving.set(false);
    }
  }

  close(): void {
    this.closed.emit();
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }
}

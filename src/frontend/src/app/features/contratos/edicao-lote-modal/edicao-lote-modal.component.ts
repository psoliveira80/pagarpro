import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import {
  ContractService,
  TituloReceberContrato,
  EdicaoLoteAcao,
} from '../../../core/services/contract.service';

@Component({
  selector: 'app-edicao-lote-modal',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent, ModalComponent],
  templateUrl: './edicao-lote-modal.component.html',
  styleUrl: './edicao-lote-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EdicaoLoteModalComponent {
  private readonly contractService = inject(ContractService);

  readonly contractId = input.required<string>();
  readonly selectedIds = input.required<Set<string>>();
  readonly installments = input.required<TituloReceberContrato[]>();

  readonly open = input(true);
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly action = signal<'postpone' | 'discount' | 'cancel'>('postpone');
  readonly actionOptions: SelectOption[] = [
    { value: 'postpone', label: 'Postergar' },
    { value: 'discount', label: 'Aplicar Desconto' },
    { value: 'cancel', label: 'Cancelar' },
  ];
  readonly days = signal(30);
  readonly discountPercent = signal(10);
  readonly isSaving = signal(false);
  readonly showConfirm = signal(false);

  selectedInstallments(): TituloReceberContrato[] {
    const ids = this.selectedIds();
    return this.installments().filter((i) => ids.has(i.id));
  }

  toggleConfirm(): void {
    this.showConfirm.set(!this.showConfirm());
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      const action = this.action();
      const params: Record<string, unknown> = {};
      if (action === 'postpone') params['days'] = this.days();
      if (action === 'discount') params['discount_percent'] = this.discountPercent();
      const acoes: EdicaoLoteAcao[] = Array.from(this.selectedIds()).map((id) => ({
        titulo_id: id,
        acao: action,
        params,
      }));
      await this.contractService.bulkEditInstallments(this.contractId(), { acoes });
      this.saved.emit();
    } catch {
      // Error handled by interceptor
    } finally {
      this.isSaving.set(false);
    }
  }

  close(): void {
    this.closed.emit();
  }

  actionLabel(action: string): string {
    const map: Record<string, string> = {
      postpone: 'Postergar',
      discount: 'Desconto',
      cancel: 'Cancelar',
    };
    return map[action] ?? action;
  }

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('pt-BR');
  }
}

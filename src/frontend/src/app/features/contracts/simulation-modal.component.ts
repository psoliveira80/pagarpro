import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../shared/components/custom-select/custom-select.component';
import {
  ContractService,
  SimulacaoResponse,
} from '../../core/services/contract.service';

@Component({
  selector: 'app-simulation-modal',
  standalone: true,
  imports: [FormsModule, CustomSelectComponent, ModalComponent],
  templateUrl: './simulation-modal.component.html',
  styleUrl: './simulation-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SimulationModalComponent {
  private readonly contractService = inject(ContractService);

  readonly open = input(true);
  readonly closed = output<void>();

  readonly value = signal(10000);
  readonly installments = signal(12);
  readonly rate = signal(1.5);
  readonly method = signal('price');
  readonly methodOptions: SelectOption[] = [
    { value: 'price', label: 'Tabela Price' },
    { value: 'sac', label: 'SAC' },
    { value: 'linear', label: 'Linear' },
  ];
  readonly isLoading = signal(false);
  readonly result = signal<SimulacaoResponse | null>(null);

  async simulate(): Promise<void> {
    this.isLoading.set(true);
    try {
      const res = await this.contractService.simulate({
        valor_total: this.value(),
        quantidade_parcelas: this.installments(),
        data_inicio: new Date().toISOString().split('T')[0],
        taxa_juros: this.rate(),
        metodo: this.method(),
      });
      this.result.set(res);
    } catch {
      this.result.set(null);
    } finally {
      this.isLoading.set(false);
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

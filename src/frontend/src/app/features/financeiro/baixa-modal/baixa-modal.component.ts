import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { InputMoedaComponent } from '../../../shared/components/input-moeda/input-moeda.component';
import {
  ReceivableService,
  TituloReceber,
} from '../../../core/services/receivable.service';

@Component({
  selector: 'app-baixa-modal',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent, ModalComponent, InputMoedaComponent],
  templateUrl: './baixa-modal.component.html',
  styleUrl: './baixa-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BaixaModalComponent implements OnInit {
  private readonly receivableService = inject(ReceivableService);

  readonly open = input(true);
  readonly receivable = input.required<TituloReceber>();
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly date = signal(new Date().toISOString().split('T')[0]);
  readonly amount = signal(0);
  readonly method = signal('pix');
  readonly fileBase64 = signal<string | null>(null);
  readonly methodOptions: SelectOption[] = [
    { value: 'pix', label: 'Pix' },
    { value: 'boleto', label: 'Boleto' },
    { value: 'transferencia', label: 'Transferência' },
    { value: 'dinheiro', label: 'Dinheiro' },
    { value: 'cartao', label: 'Cartão' },
  ];
  readonly file = signal<File | null>(null);
  readonly isPartial = signal(false);
  readonly isSaving = signal(false);

  ngOnInit(): void {
    this.amount.set(this.receivable().valor);
  }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      this.file.set(file);
      // Backend espera base64 no campo comprovante_arquivo (BaixaRequest).
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        // FileReader retorna "data:image/png;base64,XXXX" — extrai só o XXXX.
        const base64 = result.split(',')[1] ?? '';
        this.fileBase64.set(base64);
      };
      reader.readAsDataURL(file);
    }
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      if (this.isPartial()) {
        await this.receivableService.baixarParcial(this.receivable().id, {
          valor: this.amount(),
          pago_em: this.date(),
          forma_pagamento: this.method(),
        });
      } else {
        await this.receivableService.baixar(this.receivable().id, {
          valor: this.amount(),
          pago_em: this.date(),
          forma_pagamento: this.method(),
          comprovante_arquivo: this.fileBase64() ?? undefined,
        });
      }
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

  formatCurrency(value: number | null | undefined): string {
    const v = typeof value === 'number' && !isNaN(value) ? value : 0;
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
  }
}

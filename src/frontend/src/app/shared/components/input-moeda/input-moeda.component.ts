import {
  Component,
  ChangeDetectionStrategy,
  computed,
  signal,
  effect,
  forwardRef,
  inject,
  Injector,
  runInInjectionContext,
  input,
  model,
} from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-input-moeda',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './input-moeda.component.html',
  styleUrl: './input-moeda.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InputMoedaComponent {
  /** Valor numérico em reais. Ex: 1234.56 */
  readonly value = model<number>(0);
  readonly placeholder = input<string>('0,00');
  readonly disabled = input<boolean>(false);
  readonly prefix = input<string>('R$');
  readonly id = input<string>('');
  readonly ariaLabel = input<string>('Valor monetário');

  /** Texto formatado exibido no input. Sempre derivado de value(). */
  protected readonly displayValue = signal<string>('');

  private readonly injector = inject(Injector);

  constructor() {
    runInInjectionContext(this.injector, () => {
      effect(() => {
        const v = this.value();
        this.displayValue.set(this.formatFromNumber(v));
      });
    });
  }

  protected onInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const raw = input.value;
    // Mantém apenas digitos
    const digits = raw.replace(/\D/g, '');
    const numericValue = digits === '' ? 0 : Number(digits) / 100;
    const formatted = this.formatFromNumber(numericValue);
    // Atualiza visualmente
    input.value = formatted;
    this.displayValue.set(formatted);
    // Emite o número
    this.value.set(numericValue);
  }

  protected onKeyDown(event: KeyboardEvent): void {
    // Bloqueia teclas que não sejam dígitos ou controle
    const allowedKeys = [
      'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
      'Home', 'End', 'Tab', 'Enter',
    ];
    if (allowedKeys.includes(event.key)) return;
    if (event.ctrlKey || event.metaKey) return; // copy/paste/select-all
    if (!/^\d$/.test(event.key)) {
      event.preventDefault();
    }
  }

  protected onPaste(event: ClipboardEvent): void {
    event.preventDefault();
    const pasted = event.clipboardData?.getData('text') ?? '';
    const digits = pasted.replace(/\D/g, '');
    if (!digits) return;
    const numericValue = Number(digits) / 100;
    this.value.set(numericValue);
    this.displayValue.set(this.formatFromNumber(numericValue));
  }

  private formatFromNumber(n: number): string {
    if (!isFinite(n) || isNaN(n)) return '0,00';
    return n.toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
}

import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  computed,
  output,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { InputMoedaComponent } from '../../../shared/components/input-moeda/input-moeda.component';
import {
  PayableService,
  CategoriaDespesa,
  Fornecedor,
} from '../../../core/services/payable.service';

@Component({
  selector: 'app-pagamento-rapido-modal',
  standalone: true,
  imports: [FormsModule, CustomSelectComponent, ModalComponent, InputMoedaComponent],
  templateUrl: './pagamento-rapido-modal.component.html',
  styleUrl: './pagamento-rapido-modal.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PagamentoRapidoModalComponent implements OnInit {
  private readonly payableService = inject(PayableService);

  readonly open = input(true);
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly description = signal('');
  readonly supplierId = signal('');
  readonly categoryId = signal('');
  readonly amount = signal(0);
  readonly date = signal(new Date().toISOString().split('T')[0]);
  readonly method = signal('pix');
  readonly isSaving = signal(false);

  readonly methodOptions: SelectOption[] = [
    { value: 'pix', label: 'Pix' },
    { value: 'boleto', label: 'Boleto' },
    { value: 'transferencia', label: 'Transferência' },
    { value: 'dinheiro', label: 'Dinheiro' },
    { value: 'cartao', label: 'Cartão' },
  ];

  readonly categories = signal<CategoriaDespesa[]>([]);
  readonly supplierSearch = signal('');
  readonly supplierResults = signal<Fornecedor[]>([]);

  readonly categoryOptions = computed<SelectOption[]>(() =>
    this.categories().map((c) => ({ value: c.id, label: c.nome })),
  );

  ngOnInit(): void {
    this.loadCategories();
  }

  async loadCategories(): Promise<void> {
    try {
      const cats = await this.payableService.listCategories();
      this.categories.set(cats);
    } catch {
      this.categories.set([]);
    }
  }

  async searchSuppliers(term: string): Promise<void> {
    this.supplierSearch.set(term);
    if (term.length < 2) {
      this.supplierResults.set([]);
      return;
    }
    try {
      const res = await this.payableService.listSuppliers({ search: term, size: 5 });
      this.supplierResults.set(res.items);
    } catch {
      this.supplierResults.set([]);
    }
  }

  selectSupplier(supplier: Fornecedor): void {
    this.supplierId.set(supplier.id);
    this.supplierSearch.set(supplier.nome);
    this.supplierResults.set([]);
  }

  async submit(): Promise<void> {
    this.isSaving.set(true);
    try {
      await this.payableService.quickPay({
        descricao: this.description(),
        fornecedor_id: this.supplierId() || undefined,
        categoria_id: this.categoryId() || undefined,
        valor: this.amount(),
        data_vencimento: this.date(),
        data_pagamento: this.date(),
        forma_pagamento: this.method(),
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
}

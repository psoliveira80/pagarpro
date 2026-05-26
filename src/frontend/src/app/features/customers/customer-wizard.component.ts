import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReactiveFormsModule, FormControl, Validators } from '@angular/forms';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../shared/components/custom-select/custom-select.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import { ToastComponent } from '../../shared/components/toast/toast.component';
import { CustomerService, ClienteCreatePayload } from '../../core/services/customer.service';

@Component({
  selector: 'app-customer-wizard',
  standalone: true,
  imports: [ReactiveFormsModule, UiIconComponent, ToastComponent, CustomSelectComponent],
  templateUrl: './customer-wizard.component.html',
  styleUrl: './customer-wizard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CustomerWizardComponent implements OnInit {
  private readonly customerService = inject(CustomerService);
  private readonly toastService = inject(ToastService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly currentStep = signal(1);
  readonly totalSteps = 4;
  readonly isSaving = signal(false);
  readonly isEditing = signal(false);
  private editId = '';

  readonly cwStatusOptions: SelectOption[] = [
    { value: 'ativo', label: 'Ativo' },
    { value: 'inativo', label: 'Inativo' },
  ];

  readonly stateOptions: SelectOption[] = [
    { value: 'AC', label: 'AC' }, { value: 'AL', label: 'AL' }, { value: 'AP', label: 'AP' },
    { value: 'AM', label: 'AM' }, { value: 'BA', label: 'BA' }, { value: 'CE', label: 'CE' },
    { value: 'DF', label: 'DF' }, { value: 'ES', label: 'ES' }, { value: 'GO', label: 'GO' },
    { value: 'MA', label: 'MA' }, { value: 'MT', label: 'MT' }, { value: 'MS', label: 'MS' },
    { value: 'MG', label: 'MG' }, { value: 'PA', label: 'PA' }, { value: 'PB', label: 'PB' },
    { value: 'PR', label: 'PR' }, { value: 'PE', label: 'PE' }, { value: 'PI', label: 'PI' },
    { value: 'RJ', label: 'RJ' }, { value: 'RN', label: 'RN' }, { value: 'RS', label: 'RS' },
    { value: 'RO', label: 'RO' }, { value: 'RR', label: 'RR' }, { value: 'SC', label: 'SC' },
    { value: 'SP', label: 'SP' }, { value: 'SE', label: 'SE' }, { value: 'TO', label: 'TO' },
  ];

  readonly steps = [
    { number: 1, label: 'Dados Pessoais' },
    { number: 2, label: 'Contato' },
    { number: 3, label: 'Endereço' },
    { number: 4, label: 'Revisão' },
  ];

  // Step 1 — Dados Pessoais
  readonly nome_completo = new FormControl('', { validators: [Validators.required, Validators.minLength(3)], nonNullable: true });
  readonly cpf_cnpj = new FormControl('', { validators: [Validators.required], nonNullable: true });
  readonly document_type = signal<'cpf' | 'cnpj'>('cpf');
  readonly data_nascimento = new FormControl('', { nonNullable: true });
  readonly status = new FormControl<'ativo' | 'inativo'>('ativo', { nonNullable: true });

  // Step 2 — Contato
  readonly email = new FormControl('', { validators: [Validators.email], nonNullable: true });
  readonly phone = new FormControl('', { nonNullable: true });
  readonly notes = new FormControl('', { nonNullable: true });

  // Step 3 — Endereço
  readonly address_zip = new FormControl('', { nonNullable: true });
  readonly address_street = new FormControl('', { nonNullable: true });
  readonly address_number = new FormControl('', { nonNullable: true });
  readonly address_complement = new FormControl('', { nonNullable: true });
  readonly address_neighborhood = new FormControl('', { nonNullable: true });
  readonly address_city = new FormControl('', { nonNullable: true });
  readonly address_state = new FormControl('', { nonNullable: true });

  // Display values for review
  readonly cpfCnpjFormatted = signal('');

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id && id !== 'new') {
      this.isEditing.set(true);
      this.editId = id;
      this.loadCustomer(id);
    }
  }

  async loadCustomer(id: string): Promise<void> {
    try {
      const c = await this.customerService.getById(id);
      const doc = c.cpf_cnpj ?? '';
      this.nome_completo.setValue(c.nome_completo);
      this.cpf_cnpj.setValue(doc);
      this.document_type.set(doc.length === 14 ? 'cnpj' : 'cpf');
      this.data_nascimento.setValue(c.data_nascimento ?? '');
      this.status.setValue(c.status as 'ativo' | 'inativo');
      this.email.setValue(c.email ?? '');
      this.phone.setValue(c.telefone ?? '');
      this.notes.setValue(c.observacoes ?? '');
      this.address_zip.setValue(c.endereco?.cep ?? '');
      this.address_street.setValue(c.endereco?.logradouro ?? '');
      this.address_number.setValue(c.endereco?.numero ?? '');
      this.address_complement.setValue(c.endereco?.complemento ?? '');
      this.address_neighborhood.setValue(c.endereco?.bairro ?? '');
      this.address_city.setValue(c.endereco?.cidade ?? '');
      this.address_state.setValue(c.endereco?.estado ?? '');
      this.updateFormattedDoc();
    } catch {
      this.toastService.show({ message: 'Erro ao carregar cliente', type: 'error' });
      this.router.navigate(['/system/customers']);
    }
  }

  goToStep(step: number): void {
    if (step < 1 || step > this.totalSteps) return;
    if (step > this.currentStep() && !this.validateCurrentStep()) return;
    this.currentStep.set(step);
  }

  nextStep(): void {
    if (!this.validateCurrentStep()) return;
    if (this.currentStep() === this.totalSteps - 1) {
      this.updateFormattedDoc();
    }
    this.goToStep(this.currentStep() + 1);
  }

  prevStep(): void {
    this.goToStep(this.currentStep() - 1);
  }

  cancel(): void {
    this.router.navigate(['/system/customers']);
  }

  validateCurrentStep(): boolean {
    switch (this.currentStep()) {
      case 1:
        this.nome_completo.markAsTouched();
        this.cpf_cnpj.markAsTouched();
        return this.nome_completo.valid && this.cpf_cnpj.valid;
      case 2:
        this.email.markAsTouched();
        return this.email.valid;
      case 3:
        return true;
      default:
        return true;
    }
  }

  onDocumentInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '');
    const type = this.document_type();

    if (type === 'cpf') {
      value = value.slice(0, 11);
      if (value.length > 9) value = `${value.slice(0, 3)}.${value.slice(3, 6)}.${value.slice(6, 9)}-${value.slice(9)}`;
      else if (value.length > 6) value = `${value.slice(0, 3)}.${value.slice(3, 6)}.${value.slice(6)}`;
      else if (value.length > 3) value = `${value.slice(0, 3)}.${value.slice(3)}`;
    } else {
      value = value.slice(0, 14);
      if (value.length > 12) value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5, 8)}/${value.slice(8, 12)}-${value.slice(12)}`;
      else if (value.length > 8) value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5, 8)}/${value.slice(8)}`;
      else if (value.length > 5) value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5)}`;
      else if (value.length > 2) value = `${value.slice(0, 2)}.${value.slice(2)}`;
    }
    input.value = value;
    this.cpf_cnpj.setValue(value.replace(/\D/g, ''));
  }

  onPhoneInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '').slice(0, 11);
    if (value.length > 6) value = `(${value.slice(0, 2)}) ${value.slice(2, 7)}-${value.slice(7)}`;
    else if (value.length > 2) value = `(${value.slice(0, 2)}) ${value.slice(2)}`;
    input.value = value;
    this.phone.setValue(value.replace(/\D/g, ''));
  }

  onZipInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '').slice(0, 8);
    if (value.length > 5) value = `${value.slice(0, 5)}-${value.slice(5)}`;
    input.value = value;
    this.address_zip.setValue(value.replace(/\D/g, ''));
  }

  toggleDocType(): void {
    this.document_type.set(this.document_type() === 'cpf' ? 'cnpj' : 'cpf');
    this.cpf_cnpj.setValue('');
  }

  private updateFormattedDoc(): void {
    const raw = this.cpf_cnpj.value;
    if (raw.length === 11) {
      this.cpfCnpjFormatted.set(`${raw.slice(0, 3)}.${raw.slice(3, 6)}.${raw.slice(6, 9)}-${raw.slice(9)}`);
    } else if (raw.length === 14) {
      this.cpfCnpjFormatted.set(`${raw.slice(0, 2)}.${raw.slice(2, 5)}.${raw.slice(5, 8)}/${raw.slice(8, 12)}-${raw.slice(12)}`);
    } else {
      this.cpfCnpjFormatted.set(raw);
    }
  }

  async onSubmit(): Promise<void> {
    if (this.isSaving()) return;
    this.isSaving.set(true);

    try {
      const payload: ClienteCreatePayload = {
        nome_completo: this.nome_completo.value,
        cpf_cnpj: this.cpf_cnpj.value,
        email: this.email.value || undefined,
        telefone: this.phone.value || undefined,
        data_nascimento: this.data_nascimento.value || undefined,
        status: this.status.value,
        observacoes: this.notes.value || undefined,
        endereco: {
          logradouro: this.address_street.value || undefined,
          numero: this.address_number.value || undefined,
          complemento: this.address_complement.value || undefined,
          bairro: this.address_neighborhood.value || undefined,
          cidade: this.address_city.value || undefined,
          estado: this.address_state.value || undefined,
          cep: this.address_zip.value || undefined,
        },
      };

      if (this.isEditing()) {
        await this.customerService.update(this.editId, payload);
        this.toastService.show({ message: 'Cliente atualizado com sucesso', type: 'success' });
      } else {
        await this.customerService.create(payload);
        this.toastService.show({ message: 'Cliente criado com sucesso', type: 'success' });
      }
      this.router.navigate(['/system/customers']);
    } catch {
      this.toastService.show({ message: 'Erro ao salvar cliente', type: 'error' });
    } finally {
      this.isSaving.set(false);
    }
  }
}

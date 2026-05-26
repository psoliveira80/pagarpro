import {
  Component,
  ChangeDetectionStrategy,
  inject,
  input,
  output,
  signal,
  OnInit,
} from '@angular/core';
import { ReactiveFormsModule, FormGroup, FormControl, Validators } from '@angular/forms';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import { ToastService } from '../../../shared/components/toast/toast.service';
import {
  CustomerService,
  Cliente,
  ClienteCreatePayload,
} from '../../../core/services/customer.service';

@Component({
  selector: 'app-cliente-drawer',
  standalone: true,
  imports: [ReactiveFormsModule, UiIconComponent, CustomSelectComponent],
  templateUrl: './cliente-drawer.component.html',
  styleUrl: './cliente-drawer.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ClienteDrawerComponent implements OnInit {
  private readonly customerService = inject(CustomerService);
  private readonly toastService = inject(ToastService);

  readonly customer = input<Cliente | null>(null);
  readonly saved = output<void>();
  readonly closed = output<void>();

  readonly isLoading = signal(false);

  readonly docTypeOptions: SelectOption[] = [
    { value: 'cpf', label: 'CPF' },
    { value: 'cnpj', label: 'CNPJ' },
  ];

  readonly drawerStatusOptions: SelectOption[] = [
    { value: 'ativo', label: 'Ativo' },
    { value: 'inativo', label: 'Inativo' },
    { value: 'bloqueado', label: 'Bloqueado' },
  ];

  readonly form = new FormGroup({
    nome_completo: new FormControl('', {
      validators: [Validators.required, Validators.minLength(3)],
      nonNullable: true,
    }),
    document_type: new FormControl<'cpf' | 'cnpj'>('cpf', { nonNullable: true }),
    cpf_cnpj: new FormControl('', {
      validators: [Validators.required],
      nonNullable: true,
    }),
    email: new FormControl('', {
      validators: [Validators.required, Validators.email],
      nonNullable: true,
    }),
    phone: new FormControl('', {
      validators: [Validators.required],
      nonNullable: true,
    }),
    status: new FormControl<'ativo' | 'inativo' | 'bloqueado'>('ativo', { nonNullable: true }),
    address_street: new FormControl('', { nonNullable: true }),
    address_number: new FormControl('', { nonNullable: true }),
    address_complement: new FormControl('', { nonNullable: true }),
    address_neighborhood: new FormControl('', { nonNullable: true }),
    address_city: new FormControl('', { nonNullable: true }),
    address_state: new FormControl('', { nonNullable: true }),
    address_zip: new FormControl('', { nonNullable: true }),
    notes: new FormControl('', { nonNullable: true }),
  });

  get isEditing(): boolean {
    return !!this.customer();
  }

  get title(): string {
    return this.isEditing ? 'Editar Cliente' : 'Novo Cliente';
  }

  ngOnInit(): void {
    const c = this.customer();
    if (c) {
      const cpfCnpj = (c.cpf_cnpj ?? '').replace(/\D/g, '');
      const docType = cpfCnpj.length === 14 ? 'cnpj' : 'cpf';
      this.form.patchValue({
        nome_completo: c.nome_completo,
        document_type: docType as 'cpf' | 'cnpj',
        cpf_cnpj: cpfCnpj,
        email: c.email ?? '',
        phone: c.telefone ?? '',
        status: c.status as 'ativo' | 'inativo' | 'bloqueado',
        address_street: c.endereco?.logradouro ?? '',
        address_number: c.endereco?.numero ?? '',
        address_complement: c.endereco?.complemento ?? '',
        address_neighborhood: c.endereco?.bairro ?? '',
        address_city: c.endereco?.cidade ?? '',
        address_state: c.endereco?.estado ?? '',
        address_zip: c.endereco?.cep ?? '',
        notes: c.observacoes ?? '',
      });
    }
  }

  onBackdropClick(): void {
    this.closed.emit();
  }

  onDocumentInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '');
    const type = this.form.controls.document_type.value;

    if (type === 'cpf') {
      value = value.slice(0, 11);
      if (value.length > 9) {
        value = `${value.slice(0, 3)}.${value.slice(3, 6)}.${value.slice(6, 9)}-${value.slice(9)}`;
      } else if (value.length > 6) {
        value = `${value.slice(0, 3)}.${value.slice(3, 6)}.${value.slice(6)}`;
      } else if (value.length > 3) {
        value = `${value.slice(0, 3)}.${value.slice(3)}`;
      }
    } else {
      value = value.slice(0, 14);
      if (value.length > 12) {
        value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5, 8)}/${value.slice(8, 12)}-${value.slice(12)}`;
      } else if (value.length > 8) {
        value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5, 8)}/${value.slice(8)}`;
      } else if (value.length > 5) {
        value = `${value.slice(0, 2)}.${value.slice(2, 5)}.${value.slice(5)}`;
      } else if (value.length > 2) {
        value = `${value.slice(0, 2)}.${value.slice(2)}`;
      }
    }

    input.value = value;
    this.form.controls.cpf_cnpj.setValue(value.replace(/\D/g, ''));
  }

  onPhoneInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '').slice(0, 11);

    if (value.length > 6) {
      value = `(${value.slice(0, 2)}) ${value.slice(2, 7)}-${value.slice(7)}`;
    } else if (value.length > 2) {
      value = `(${value.slice(0, 2)}) ${value.slice(2)}`;
    }

    input.value = value;
    this.form.controls.phone.setValue(value.replace(/\D/g, ''));
  }

  onZipInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '').slice(0, 8);

    if (value.length > 5) {
      value = `${value.slice(0, 5)}-${value.slice(5)}`;
    }

    input.value = value;
    this.form.controls.address_zip.setValue(value.replace(/\D/g, ''));
  }

  async onSubmit(): Promise<void> {
    if (this.form.invalid || this.isLoading()) return;

    this.isLoading.set(true);

    try {
      const formValues = this.form.getRawValue();
      const payload: ClienteCreatePayload = {
        nome_completo: formValues.nome_completo,
        cpf_cnpj: formValues.cpf_cnpj,
        email: formValues.email || undefined,
        telefone: formValues.phone || undefined,
        status: formValues.status,
        observacoes: formValues.notes || undefined,
        endereco: {
          logradouro: formValues.address_street || undefined,
          numero: formValues.address_number || undefined,
          complemento: formValues.address_complement || undefined,
          bairro: formValues.address_neighborhood || undefined,
          cidade: formValues.address_city || undefined,
          estado: formValues.address_state || undefined,
          cep: formValues.address_zip || undefined,
        },
      };
      const c = this.customer();

      if (c) {
        await this.customerService.update(c.id, payload);
        this.toastService.show({ message: 'Cliente atualizado com sucesso', type: 'success' });
      } else {
        await this.customerService.create(payload);
        this.toastService.show({ message: 'Cliente criado com sucesso', type: 'success' });
      }

      this.saved.emit();
    } catch {
      this.toastService.show({ message: 'Erro ao salvar cliente', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }
}

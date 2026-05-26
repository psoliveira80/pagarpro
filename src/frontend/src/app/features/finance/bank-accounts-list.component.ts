import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../shared/components/custom-select/custom-select.component';
import {
  BankService,
  ContaBancaria,
  ContaBancariaCreatePayload,
} from '../../core/services/bank.service';
import { ConfirmService } from '../../shared/services/confirm.service';

@Component({
  selector: 'app-bank-accounts-list',
  standalone: true,
  imports: [FormsModule, UiIconComponent, CustomSelectComponent, ModalComponent],
  templateUrl: './bank-accounts-list.component.html',
  styleUrl: './bank-accounts-list.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BankAccountsListComponent implements OnInit {
  private readonly bankService = inject(BankService);
  private readonly confirmService = inject(ConfirmService);

  readonly accounts = signal<ContaBancaria[]>([]);
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly showForm = signal(false);
  readonly editingAccount = signal<ContaBancaria | null>(null);

  // Form fields
  readonly formName = signal('');
  readonly formBankCode = signal('');
  readonly formBankName = signal('');
  readonly formAgency = signal('');
  readonly formAccountNumber = signal('');
  readonly formAccountType = signal('corrente');

  readonly accountTypeOptions: SelectOption[] = [
    { value: 'corrente', label: 'Conta Corrente' },
    { value: 'poupanca', label: 'Poupança' },
    { value: 'pagamento', label: 'Conta Pagamento' },
  ];

  async ngOnInit(): Promise<void> {
    await this.loadAccounts();
  }

  async loadAccounts(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const data = await this.bankService.listAccounts(false);
      this.accounts.set(data);
    } catch {
      this.error.set('Erro ao carregar contas bancárias');
    } finally {
      this.isLoading.set(false);
    }
  }

  openNewForm(): void {
    this.editingAccount.set(null);
    this.formName.set('');
    this.formBankCode.set('');
    this.formBankName.set('');
    this.formAgency.set('');
    this.formAccountNumber.set('');
    this.formAccountType.set('corrente');
    this.showForm.set(true);
  }

  openEditForm(account: ContaBancaria): void {
    this.editingAccount.set(account);
    this.formName.set(account.nome);
    this.formBankCode.set(account.codigo_banco || '');
    this.formBankName.set(account.nome_banco || '');
    this.formAgency.set(account.agencia || '');
    this.formAccountNumber.set(account.numero_conta || '');
    this.formAccountType.set(account.tipo);
    this.showForm.set(true);
  }

  closeForm(): void {
    this.showForm.set(false);
    this.editingAccount.set(null);
  }

  async saveAccount(): Promise<void> {
    const payload: ContaBancariaCreatePayload = {
      nome: this.formName(),
      codigo_banco: this.formBankCode() || undefined,
      nome_banco: this.formBankName() || undefined,
      agencia: this.formAgency() || undefined,
      numero_conta: this.formAccountNumber() || undefined,
      tipo: this.formAccountType(),
    };

    try {
      const editing = this.editingAccount();
      if (editing) {
        await this.bankService.updateAccount(editing.id, payload);
      } else {
        await this.bankService.createAccount(payload);
      }
      this.closeForm();
      await this.loadAccounts();
    } catch {
      this.error.set('Erro ao salvar conta bancária');
    }
  }

  async toggleActive(account: ContaBancaria): Promise<void> {
    try {
      await this.bankService.updateAccount(account.id, {
        ...({ is_active: !account.ativo } as Record<string, unknown>),
      } as Partial<ContaBancariaCreatePayload>);
      await this.loadAccounts();
    } catch {
      this.error.set('Erro ao atualizar status');
    }
  }

  async deleteAccount(account: ContaBancaria): Promise<void> {
    const ok = await this.confirmService.confirm({ text: 'Deseja realmente desativar esta conta bancária?', type: 'danger' });
    if (!ok) return;
    try {
      await this.bankService.deleteAccount(account.id);
      await this.loadAccounts();
    } catch {
      this.error.set('Erro ao excluir conta');
    }
  }
}

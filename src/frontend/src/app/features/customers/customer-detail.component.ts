import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import {
  CustomerService,
  Cliente,
} from '../../core/services/customer.service';
import { AdminService } from '../../core/services/admin.service';
import { AssetsListComponent } from './assets-list.component';
import { CustomerDashboardTabComponent } from './customer-dashboard-tab.component';

@Component({
  selector: 'app-customer-detail',
  standalone: true,
  imports: [UiIconComponent, AssetsListComponent, CustomerDashboardTabComponent, ModalComponent],
  templateUrl: './customer-detail.component.html',
  styleUrl: './customer-detail.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CustomerDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly customerService = inject(CustomerService);
  private readonly toastService = inject(ToastService);
  private readonly adminService = inject(AdminService);

  readonly customer = signal<Cliente | null>(null);
  readonly isLoading = signal(true);
  readonly activeTab = signal<'dados' | 'contratos' | 'financeiro' | 'ativos' | 'anexos' | 'dashboard'>('dados');
  readonly showDeleteConfirm = signal(false);
  readonly isDeleting = signal(false);
  readonly isExporting = signal(false);
  readonly isAnonymizing = signal(false);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadCustomer(id);
    }
  }

  async loadCustomer(id: string): Promise<void> {
    this.isLoading.set(true);
    try {
      const c = await this.customerService.getById(id);
      this.customer.set(c);
    } catch {
      this.toastService.show({ message: 'Erro ao carregar cliente', type: 'error' });
      this.router.navigate(['/system/customers']);
    } finally {
      this.isLoading.set(false);
    }
  }

  setTab(tab: 'dados' | 'contratos' | 'financeiro' | 'ativos' | 'anexos' | 'dashboard'): void {
    this.activeTab.set(tab);
  }

  editCustomer(): void {
    const c = this.customer();
    if (c) {
      this.router.navigate(['/system/customers', c.id, 'edit']);
    }
  }

  confirmDelete(): void {
    this.showDeleteConfirm.set(true);
  }

  cancelDelete(): void {
    this.showDeleteConfirm.set(false);
  }

  async deleteCustomer(): Promise<void> {
    const c = this.customer();
    if (!c) return;

    this.isDeleting.set(true);
    try {
      await this.customerService.delete(c.id);
      this.toastService.show({ message: 'Cliente removido com sucesso', type: 'success' });
      this.router.navigate(['/system/customers']);
    } catch {
      this.toastService.show({ message: 'Erro ao remover cliente', type: 'error' });
    } finally {
      this.isDeleting.set(false);
      this.showDeleteConfirm.set(false);
    }
  }

  goBack(): void {
    this.router.navigate(['/system/customers']);
  }

  // ── LGPD (Story 9-10) ──

  async exportCustomerData(): Promise<void> {
    const c = this.customer();
    if (!c) return;
    this.isExporting.set(true);
    try {
      const response = await fetch(`/api/v1/customers/${c.id}/my-data`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}` },
      });
      if (!response.ok) throw new Error('Export failed');
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dados-${c.cpf_cnpj}-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.toastService.show({ message: 'Dados exportados com sucesso', type: 'success' });
    } catch {
      this.toastService.show({ message: 'Erro ao exportar dados', type: 'error' });
    } finally {
      this.isExporting.set(false);
    }
  }

  async requestAnonymization(): Promise<void> {
    const c = this.customer();
    if (!c) return;
    const reason = prompt('Motivo da anonimização (LGPD):');
    if (!reason) return;
    this.isAnonymizing.set(true);
    try {
      const response = await fetch(`/api/v1/customers/${c.id}/anonymize`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
        },
        body: JSON.stringify({ reason }),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail ?? 'Failed');
      }
      this.toastService.show({ message: 'Dados anonimizados com sucesso', type: 'success' });
      await this.loadCustomer(c.id);
    } catch (e) {
      this.toastService.show({ message: `Erro: ${e instanceof Error ? e.message : 'Falha na anonimização'}`, type: 'error' });
    } finally {
      this.isAnonymizing.set(false);
    }
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      ativo: 'Ativo',
      inativo: 'Inativo',
      bloqueado: 'Bloqueado',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      ativo: 'bg-green-500/20 text-green-400',
      inativo: 'bg-yellow-500/20 text-yellow-400',
      bloqueado: 'bg-red-500/20 text-red-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  scoreClass(score: number): string {
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }

  documentTypeLabel(customer: Cliente): string {
    const doc = (customer.cpf_cnpj ?? '').replace(/\D/g, '');
    return doc.length === 14 ? 'CNPJ' : 'CPF';
  }

  formatDocument(customer: Cliente): string {
    const doc = (customer.cpf_cnpj ?? '').replace(/\D/g, '');
    if (doc.length === 11) {
      return `${doc.slice(0, 3)}.${doc.slice(3, 6)}.${doc.slice(6, 9)}-${doc.slice(9)}`;
    }
    if (doc.length === 14) {
      return `${doc.slice(0, 2)}.${doc.slice(2, 5)}.${doc.slice(5, 8)}/${doc.slice(8, 12)}-${doc.slice(12)}`;
    }
    return doc;
  }

  formatPhone(phone: string | null): string {
    if (!phone) return '';
    const digits = phone.replace(/\D/g, '');
    if (digits.length === 11) {
      return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
    }
    if (digits.length === 10) {
      return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
    }
    return phone;
  }
}

import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import {
  ConversationService,
  Broadcast,
} from '../../core/services/conversation.service';
import { CustomerService, Cliente } from '../../core/services/customer.service';
import { ToastService } from '../../shared/components/toast/toast.service';
import { ToastComponent } from '../../shared/components/toast/toast.component';

interface ChannelOption {
  id: string;
  name: string;
  icon: string;
  configured: boolean;
  healthy: boolean;
  comingSoon?: boolean;
}

@Component({
  selector: 'app-broadcast-list',
  standalone: true,
  imports: [UiIconComponent, DatePipe, ToastComponent, ModalComponent],
  templateUrl: './broadcast-list.component.html',
  styleUrl: './broadcast-list.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BroadcastListComponent implements OnInit {
  private readonly conversationService = inject(ConversationService);
  private readonly customerService = inject(CustomerService);
  private readonly toastService = inject(ToastService);
  private readonly router = inject(Router);

  readonly broadcasts = signal<Broadcast[]>([]);
  readonly isLoading = signal(true);

  // Create modal
  readonly showCreateModal = signal(false);
  readonly isSaving = signal(false);
  readonly formName = signal('');
  readonly formTemplate = signal('');

  // Send wizard
  readonly showSendWizard = signal(false);
  readonly sendStep = signal(1); // 1=recipients, 2=channel, 3=preview+confirm
  readonly sendingBroadcast = signal<Broadcast | null>(null);
  readonly isSending = signal(false);

  // Step 1: Recipients
  readonly customerSearch = signal('');
  readonly allCustomers = signal<Cliente[]>([]);
  readonly selectedCustomerIds = signal<Set<string>>(new Set());
  readonly isLoadingCustomers = signal(false);
  readonly selectAll = signal(false);

  // Step 2: Channel
  readonly channels = signal<ChannelOption[]>([
    { id: 'whatsapp', name: 'WhatsApp', icon: 'heroChatBubbleLeftRight', configured: false, healthy: false },
    { id: 'email', name: 'E-mail', icon: 'heroPaperAirplane', configured: false, healthy: false },
    { id: 'sms', name: 'SMS', icon: 'heroInboxStack', configured: false, healthy: false },
  ]);
  readonly selectedChannel = signal('');

  readonly selectedCount = computed(() => this.selectedCustomerIds().size);
  readonly hasConfiguredChannel = computed(() => this.channels().some((c) => c.configured));

  ngOnInit(): void {
    this.loadBroadcasts();
    this.loadChannelStatus();
  }

  async loadBroadcasts(): Promise<void> {
    this.isLoading.set(true);
    try {
      const items = await this.conversationService.listBroadcasts({ size: 50 });
      this.broadcasts.set(items ?? []);
    } catch {
      this.broadcasts.set([]);
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadChannelStatus(): Promise<void> {
    try {
      const channelList = await this.conversationService.listChannels();
      const mapped: ChannelOption[] = channelList.map((ch: Record<string, unknown>) => ({
        id: ch['channel_type'] as string,
        name: ch['label'] as string,
        icon: ch['channel_type'] === 'whatsapp' ? 'heroChatBubbleLeftRight'
            : ch['channel_type'] === 'email' ? 'heroPaperAirplane'
            : 'heroInboxStack',
        configured: ch['configured'] as boolean,
        healthy: (ch['healthy'] as boolean) ?? false,
        comingSoon: (ch['coming_soon'] as boolean) ?? false,
      }));
      this.channels.set(mapped);
    } catch {
      // Keep defaults
    }
  }

  // --- Create Modal ---

  openCreateModal(): void {
    this.formName.set('');
    this.formTemplate.set('');
    this.showCreateModal.set(true);
  }

  closeCreateModal(): void {
    this.showCreateModal.set(false);
  }

  async saveAviso(): Promise<void> {
    const name = this.formName().trim();
    const template = this.formTemplate().trim();
    if (!name || !template) return;

    this.isSaving.set(true);
    try {
      await this.conversationService.createBroadcast({ name, template });
      this.toastService.show({ message: 'Aviso criado como rascunho', type: 'success' });
      this.closeCreateModal();
      await this.loadBroadcasts();
    } catch {
      this.toastService.show({ message: 'Erro ao criar aviso', type: 'error' });
    } finally {
      this.isSaving.set(false);
    }
  }

  // --- Send Wizard ---

  openSendWizard(broadcast: Broadcast): void {
    this.sendingBroadcast.set(broadcast);
    this.sendStep.set(1);
    this.selectedCustomerIds.set(new Set());
    this.selectedChannel.set('');
    this.selectAll.set(false);
    this.showSendWizard.set(true);
    this.loadCustomers('');
  }

  closeSendWizard(): void {
    this.showSendWizard.set(false);
    this.sendingBroadcast.set(null);
  }

  async loadCustomers(search: string): Promise<void> {
    this.customerSearch.set(search);
    this.isLoadingCustomers.set(true);
    try {
      const res = await this.customerService.list({ search: search || undefined, status: 'ativo', size: 100 });
      this.allCustomers.set(res?.items ?? []);
    } catch {
      this.allCustomers.set([]);
    } finally {
      this.isLoadingCustomers.set(false);
    }
  }

  toggleCustomer(id: string): void {
    const current = new Set(this.selectedCustomerIds());
    if (current.has(id)) {
      current.delete(id);
    } else {
      current.add(id);
    }
    this.selectedCustomerIds.set(current);
    this.selectAll.set(current.size === this.allCustomers().length);
  }

  toggleSelectAll(): void {
    if (this.selectAll()) {
      this.selectedCustomerIds.set(new Set());
      this.selectAll.set(false);
    } else {
      const all = new Set(this.allCustomers().map((c) => c.id));
      this.selectedCustomerIds.set(all);
      this.selectAll.set(true);
    }
  }

  isCustomerSelected(id: string): boolean {
    return this.selectedCustomerIds().has(id);
  }

  selectChannel(id: string): void {
    const ch = this.channels().find((c) => c.id === id);
    if (ch?.configured) {
      this.selectedChannel.set(id);
    }
  }

  nextSendStep(): void {
    if (this.sendStep() === 1 && this.selectedCount() === 0) return;
    if (this.sendStep() === 2 && !this.selectedChannel()) return;
    this.sendStep.update((s) => Math.min(s + 1, 3));
  }

  prevSendStep(): void {
    this.sendStep.update((s) => Math.max(s - 1, 1));
  }

  previewMessage(): string {
    const tpl = this.sendingBroadcast()?.template ?? '';
    const first = this.allCustomers().find((c) => this.selectedCustomerIds().has(c.id));
    if (!first) return tpl;
    return tpl
      .replace(/\{nome\}/g, first.nome_completo)
      .replace(/\{valor\}/g, 'R$ 380,00')
      .replace(/\{data_vencimento\}/g, '20/05/2026');
  }

  channelLabel(): string {
    return this.channels().find((c) => c.id === this.selectedChannel())?.name ?? '';
  }

  async confirmSend(): Promise<void> {
    const b = this.sendingBroadcast();
    if (!b) return;

    this.isSending.set(true);
    try {
      await this.conversationService.sendBroadcast(b.id);
      this.toastService.show({
        message: `Aviso enviado para ${this.selectedCount()} destinatário(s) via ${this.channelLabel()}`,
        type: 'success',
      });
      this.closeSendWizard();
      await this.loadBroadcasts();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao enviar aviso';
      this.toastService.show({ message: msg, type: 'error' });
    } finally {
      this.isSending.set(false);
    }
  }

  // --- Navigation ---

  goBack(): void {
    this.router.navigate(['/system/inbox']);
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      draft: 'Rascunho',
      scheduled: 'Agendado',
      sending: 'Enviando',
      sent: 'Enviado',
      failed: 'Falhou',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      draft: 'bg-gray-500/20 text-gray-400',
      scheduled: 'bg-blue-500/20 text-blue-400',
      sending: 'bg-yellow-500/20 text-yellow-400',
      sent: 'bg-green-500/20 text-green-400',
      failed: 'bg-red-500/20 text-red-400',
    };
    return map[status] ?? 'bg-gray-500/20 text-gray-400';
  }

  formatDocument(c: Cliente): string {
    const doc = (c.cpf_cnpj ?? '').replace(/\D/g, '');
    if (doc.length === 11) return `${doc.slice(0, 3)}.${doc.slice(3, 6)}.${doc.slice(6, 9)}-${doc.slice(9)}`;
    if (doc.length === 14) return `${doc.slice(0, 2)}.${doc.slice(2, 5)}.${doc.slice(5, 8)}/${doc.slice(8, 12)}-${doc.slice(12)}`;
    return doc;
  }
}

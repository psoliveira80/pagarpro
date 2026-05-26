import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
  OnDestroy,
  DestroyRef,
} from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import {
  ConversationService,
  Conversation,
  ConversationMessage,
} from '../../core/services/conversation.service';

@Component({
  selector: 'app-whatsapp-inbox',
  standalone: true,
  imports: [UiIconComponent, DatePipe, FormsModule],
  templateUrl: './whatsapp-inbox.component.html',
  styleUrl: './whatsapp-inbox.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WhatsappInboxComponent implements OnInit, OnDestroy {
  private readonly conversationService = inject(ConversationService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private pollingTimer: ReturnType<typeof setInterval> | null = null;

  readonly conversations = signal<Conversation[]>([]);
  readonly selectedConversation = signal<Conversation | null>(null);
  readonly messages = signal<ConversationMessage[]>([]);
  readonly isLoadingList = signal(true);
  readonly isLoadingMessages = signal(false);
  readonly isSending = signal(false);
  readonly messageInput = signal('');
  readonly showContextPanel = signal(false);
  readonly filterStatus = signal<string>('all');

  readonly filteredConversations = computed(() => {
    const status = this.filterStatus();
    const list = this.conversations();
    if (status === 'all') return list;
    return list.filter((c) => c.status === status);
  });

  ngOnInit(): void {
    this.loadConversations();
    this.pollingTimer = setInterval(() => {
      this.pollConversations();
    }, 5000);
    this.destroyRef.onDestroy(() => {
      if (this.pollingTimer) clearInterval(this.pollingTimer);
    });
  }

  ngOnDestroy(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  async loadConversations(): Promise<void> {
    this.isLoadingList.set(true);
    try {
      const res = await this.conversationService.list({ size: 50 });
      this.conversations.set(res.items);
    } catch {
      // Silent fail — polling will retry
    } finally {
      this.isLoadingList.set(false);
    }
  }

  private async pollConversations(): Promise<void> {
    try {
      const res = await this.conversationService.list({ size: 50 });
      this.conversations.set(res.items);

      const selected = this.selectedConversation();
      if (selected) {
        const msgs = await this.conversationService.getMessages(selected.id);
        this.messages.set(msgs);
      }
    } catch {
      // Silent fail
    }
  }

  async selectConversation(conv: Conversation): Promise<void> {
    this.selectedConversation.set(conv);
    this.isLoadingMessages.set(true);
    try {
      const msgs = await this.conversationService.getMessages(conv.id);
      this.messages.set(msgs);
    } catch {
      this.messages.set([]);
    } finally {
      this.isLoadingMessages.set(false);
    }
  }

  async sendMessage(): Promise<void> {
    const conv = this.selectedConversation();
    const content = this.messageInput().trim();
    if (!conv || !content) return;

    this.isSending.set(true);
    try {
      await this.conversationService.sendMessage(conv.id, { content });
      this.messageInput.set('');
      const msgs = await this.conversationService.getMessages(conv.id);
      this.messages.set(msgs);
    } catch {
      // Handle error silently
    } finally {
      this.isSending.set(false);
    }
  }

  async takeover(): Promise<void> {
    const conv = this.selectedConversation();
    if (!conv) return;
    try {
      const updated = await this.conversationService.takeover(conv.id);
      this.selectedConversation.set(updated);
      this.updateConversationInList(updated);
    } catch {
      // Handle error
    }
  }

  async resumeAgent(): Promise<void> {
    const conv = this.selectedConversation();
    if (!conv) return;
    try {
      const updated = await this.conversationService.resumeAgent(conv.id);
      this.selectedConversation.set(updated);
      this.updateConversationInList(updated);
    } catch {
      // Handle error
    }
  }

  private updateConversationInList(updated: Conversation): void {
    this.conversations.update((list) =>
      list.map((c) => (c.id === updated.id ? updated : c)),
    );
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  toggleContextPanel(): void {
    this.showContextPanel.update((v) => !v);
  }

  statusColor(conv: Conversation): string {
    switch (conv.status) {
      case 'active':
        return 'bg-green-500';
      case 'waiting':
        return 'bg-yellow-500';
      case 'closed':
        return 'bg-gray-500';
      case 'manual':
        return 'bg-blue-500';
      default:
        return 'bg-red-500';
    }
  }

  statusLabel(conv: Conversation): string {
    const map: Record<string, string> = {
      active: 'Ativo',
      waiting: 'Aguardando',
      closed: 'Fechado',
      manual: 'Manual',
    };
    return map[conv.status] ?? conv.status;
  }

  navigateToBroadcasts(): void {
    this.router.navigate(['/system/inbox/broadcasts']);
  }

  scoreClass(score: number): string {
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }
}

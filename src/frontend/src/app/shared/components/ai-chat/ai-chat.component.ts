import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  ElementRef,
  ViewChild,
  AfterViewChecked,
} from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { UiIconComponent } from '../icon/icon.component';
import {
  AgentService,
  AgentChatChunk,
  AgentAction,
} from '../../../core/services/agent.service';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  confidence?: 'alta' | 'media' | 'baixa';
  actions?: AgentAction[];
  isStreaming?: boolean;
}

@Component({
  selector: 'app-ai-chat',
  standalone: true,
  imports: [UiIconComponent, FormsModule],
  templateUrl: './ai-chat.component.html',
  styleUrl: './ai-chat.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AiChatComponent implements AfterViewChecked {
  private readonly agentService = inject(AgentService);
  private readonly router = inject(Router);
  private shouldScrollToBottom = false;

  @ViewChild('messagesContainer') messagesContainer?: ElementRef<HTMLDivElement>;

  readonly isOpen = signal(false);
  readonly messages = signal<ChatMessage[]>([]);
  readonly inputText = signal('');
  readonly isThinking = signal(false);
  readonly hasSuggestion = signal(true);

  readonly isEmpty = computed(() => this.messages().length === 0);

  readonly suggestions = [
    { text: 'Inadimplentes hoje', icon: 'heroExclamationTriangle' },
    { text: 'Receita do mês', icon: 'heroCurrencyDollar' },
    { text: 'Resumo da frota', icon: 'heroTruck' },
    { text: 'Contratos vencendo', icon: 'heroDocumentText' },
  ];

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  toggle(): void {
    this.isOpen.update((v) => !v);
    if (this.isOpen()) {
      this.hasSuggestion.set(false);
    }
  }

  close(): void {
    this.isOpen.set(false);
  }

  sendSuggestion(text: string): void {
    this.inputText.set(text);
    this.send();
  }

  send(): void {
    const content = this.inputText().trim();
    if (!content || this.isThinking()) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    };

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    this.messages.update((msgs) => [...msgs, userMsg, assistantMsg]);
    this.inputText.set('');
    this.isThinking.set(true);
    this.shouldScrollToBottom = true;

    this.agentService.chat({ message: content }).subscribe({
      next: (chunk: AgentChatChunk) => {
        if (chunk.type === 'token' && chunk.content) {
          this.messages.update((msgs) =>
            msgs.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, content: m.content + chunk.content }
                : m,
            ),
          );
          this.shouldScrollToBottom = true;
        } else if (chunk.type === 'metadata') {
          this.messages.update((msgs) =>
            msgs.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    confidence: chunk.confidence,
                    actions: chunk.actions,
                  }
                : m,
            ),
          );
        } else if (chunk.type === 'error') {
          this.messages.update((msgs) =>
            msgs.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content: chunk.error ?? 'Erro ao processar resposta',
                    isStreaming: false,
                  }
                : m,
            ),
          );
        }
      },
      complete: () => {
        this.messages.update((msgs) =>
          msgs.map((m) =>
            m.id === assistantMsg.id ? { ...m, isStreaming: false } : m,
          ),
        );
        this.isThinking.set(false);
        this.shouldScrollToBottom = true;
      },
    });
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  executeAction(action: AgentAction): void {
    if (action.route) {
      this.router.navigate([action.route]);
      this.close();
    }
  }

  confidenceLabel(confidence?: string): string {
    const map: Record<string, string> = {
      alta: 'Alta',
      media: 'Média',
      baixa: 'Baixa',
    };
    return map[confidence ?? ''] ?? '';
  }

  confidenceClass(confidence?: string): string {
    const map: Record<string, string> = {
      alta: 'bg-green-500/20 text-green-400',
      media: 'bg-yellow-500/20 text-yellow-400',
      baixa: 'bg-red-500/20 text-red-400',
    };
    return map[confidence ?? ''] ?? '';
  }

  clearChat(): void {
    this.messages.set([]);
  }

  private scrollToBottom(): void {
    const el = this.messagesContainer?.nativeElement;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }
}

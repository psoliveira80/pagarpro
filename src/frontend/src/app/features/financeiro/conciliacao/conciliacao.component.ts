import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { CustomSelectComponent, SelectOption } from '../../../shared/components/custom-select/custom-select.component';
import {
  BankService,
  ContaBancaria,
  TransacaoBancaria,
  SugestaoConciliacao,
  DivergenciasResponse,
} from '../../../core/services/bank.service';
import { ReceivableService, TituloReceber } from '../../../core/services/receivable.service';
import { PayableService, TituloPagar } from '../../../core/services/payable.service';

@Component({
  selector: 'app-conciliacao',
  standalone: true,
  imports: [FormsModule, RouterLink, UiIconComponent, CustomSelectComponent, ModalComponent],
  templateUrl: './conciliacao.component.html',
  styleUrl: './conciliacao.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConciliacaoComponent implements OnInit {
  private readonly bankService = inject(BankService);
  private readonly receivableService = inject(ReceivableService);
  private readonly payableService = inject(PayableService);

  // Data
  readonly accounts = signal<ContaBancaria[]>([]);
  readonly selectedAccountId = signal('');
  readonly transactions = signal<TransacaoBancaria[]>([]);
  readonly receivables = signal<TituloReceber[]>([]);
  readonly payables = signal<TituloPagar[]>([]);
  readonly suggestions = signal<SugestaoConciliacao[]>([]);
  readonly divergences = signal<DivergenciasResponse | null>(null);

  // UI state
  readonly isLoading = signal(false);
  readonly error = signal('');
  readonly successMessage = signal('');
  readonly selectedTxIds = signal<Set<string>>(new Set());
  readonly selectedTargetId = signal('');
  readonly selectedTargetKind = signal('');
  readonly showMatchConfirm = signal(false);
  readonly activeTab = signal<'transactions' | 'import'>('transactions');

  readonly accountOptions = signal<SelectOption[]>([]);

  // Indicators
  readonly pendingTxCount = computed(() =>
    this.transactions().filter((t) => t.status === 'pendente').length,
  );
  readonly pendingTitlesCount = computed(() =>
    this.receivables().length + this.payables().filter((p) => p.status === 'pendente').length,
  );
  readonly totalDivergences = computed(() => {
    const d = this.divergences();
    if (!d) return 0;
    return d.total_orfas + d.total_suspeitos + d.total_divergencias;
  });

  // Suggestion map for quick lookup
  readonly suggestionMap = computed(() => {
    const map = new Map<string, SugestaoConciliacao>();
    for (const s of this.suggestions()) {
      map.set(s.transacao_id, s);
    }
    return map;
  });

  async ngOnInit(): Promise<void> {
    await this.loadAccounts();
  }

  private async loadAccounts(): Promise<void> {
    try {
      const accts = await this.bankService.listAccounts();
      this.accounts.set(accts);
      this.accountOptions.set(
        accts.map((a) => ({ value: a.id, label: `${a.nome}${a.nome_banco ? ' - ' + a.nome_banco : ''}` })),
      );
      if (accts.length > 0) {
        this.selectedAccountId.set(accts[0].id);
        await this.loadData();
      }
    } catch {
      this.error.set('Erro ao carregar contas');
    }
  }

  async onAccountChange(accountId: string): Promise<void> {
    this.selectedAccountId.set(accountId);
    await this.loadData();
  }

  async loadData(): Promise<void> {
    this.isLoading.set(true);
    this.error.set('');
    try {
      const [txResult, suggestions, divergences] = await Promise.all([
        this.bankService.listTransactions({
          conta_id: this.selectedAccountId(),
          status: 'pendente',
          size: 100,
        }),
        this.bankService.getMatchSuggestions(this.selectedAccountId()),
        this.bankService.getDivergences(),
      ]);

      this.transactions.set(txResult.items);
      this.suggestions.set(suggestions.sugestoes);
      this.divergences.set(divergences);

      // Load receivables and payables for the right pane
      try {
        const recResult = await this.receivableService.list({
          status: 'pago_aguardando_verificacao',
          size: 100,
        });
        this.receivables.set(recResult.items || []);
      } catch {
        this.receivables.set([]);
      }

      try {
        const payResult = await this.payableService.listPayables({
          status: 'pendente',
          size: 100,
        });
        this.payables.set(payResult.items || []);
      } catch {
        this.payables.set([]);
      }
    } catch {
      this.error.set('Erro ao carregar dados de conciliação');
    } finally {
      this.isLoading.set(false);
    }
  }

  toggleTxSelection(txId: string): void {
    const current = new Set(this.selectedTxIds());
    if (current.has(txId)) {
      current.delete(txId);
    } else {
      current.add(txId);
    }
    this.selectedTxIds.set(current);
  }

  isTxSelected(txId: string): boolean {
    return this.selectedTxIds().has(txId);
  }

  getSuggestionForTx(txId: string): SugestaoConciliacao | undefined {
    return this.suggestionMap().get(txId);
  }

  selectTarget(kind: string, id: string): void {
    this.selectedTargetKind.set(kind);
    this.selectedTargetId.set(id);

    if (this.selectedTxIds().size > 0) {
      this.showMatchConfirm.set(true);
    }
  }

  acceptSuggestion(suggestion: SugestaoConciliacao): void {
    this.selectedTxIds.set(new Set([suggestion.transacao_id]));
    this.selectedTargetKind.set(suggestion.tipo_destino);
    this.selectedTargetId.set(suggestion.destino_id);
    this.showMatchConfirm.set(true);
  }

  async acceptAllSuggestions(): Promise<void> {
    const highConfidence = this.suggestions().filter((s) => s.pontuacao >= 0.85);
    if (highConfidence.length === 0) {
      this.error.set('Nenhuma sugestão com alta confiança');
      return;
    }

    this.isLoading.set(true);
    this.error.set('');
    let totalMatched = 0;

    try {
      for (const s of highConfidence) {
        const result = await this.bankService.confirmMatch({
          transacao_ids: [s.transacao_id],
          tipo_destino: s.tipo_destino,
          destino_id: s.destino_id,
        });
        totalMatched += result.quantidade_conciliada;
      }
      this.successMessage.set(`${totalMatched} transações conciliadas automaticamente`);
      await this.loadData();
      setTimeout(() => this.successMessage.set(''), 5000);
    } catch {
      this.error.set('Erro ao conciliar em lote');
    } finally {
      this.isLoading.set(false);
    }
  }

  async confirmMatch(): Promise<void> {
    if (this.selectedTxIds().size === 0 || !this.selectedTargetId()) return;

    this.isLoading.set(true);
    this.error.set('');
    try {
      const result = await this.bankService.confirmMatch({
        transacao_ids: Array.from(this.selectedTxIds()),
        tipo_destino: this.selectedTargetKind(),
        destino_id: this.selectedTargetId(),
      });
      this.successMessage.set(`${result.quantidade_conciliada} transação(ões) conciliada(s)`);
      this.showMatchConfirm.set(false);
      this.selectedTxIds.set(new Set());
      this.selectedTargetId.set('');
      await this.loadData();
      setTimeout(() => this.successMessage.set(''), 5000);
    } catch {
      this.error.set('Erro ao confirmar conciliação');
    } finally {
      this.isLoading.set(false);
    }
  }

  cancelMatch(): void {
    this.showMatchConfirm.set(false);
  }

  async ignoreTransaction(txId: string): Promise<void> {
    try {
      await this.bankService.ignoreTransaction(txId);
      await this.loadData();
    } catch {
      this.error.set('Erro ao ignorar transação');
    }
  }
}

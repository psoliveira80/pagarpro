import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgClass, DatePipe, DecimalPipe } from '@angular/common';
import {
  Comprovante,
  ComprovantesService,
  StatusComprovante,
} from '../../../core/services/comprovantes.service';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { ConfirmService } from '../../../shared/services/confirm.service';
import { ComprovanteDetalheComponent } from '../comprovante-detalhe/comprovante-detalhe.component';

@Component({
  selector: 'app-comprovantes-lista',
  standalone: true,
  imports: [FormsModule, NgClass, DatePipe, DecimalPipe, ComprovanteDetalheComponent],
  templateUrl: './comprovantes-lista.component.html',
  styleUrl: './comprovantes-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComprovantesListaComponent implements OnInit {
  private readonly service = inject(ComprovantesService);
  private readonly toast = inject(ToastService);
  private readonly confirmService = inject(ConfirmService);

  readonly carregando = signal(true);
  readonly erro = signal<string | null>(null);
  readonly comprovantes = signal<Comprovante[]>([]);
  readonly total = signal(0);

  readonly filtroStatus = signal<StatusComprovante | ''>('');
  readonly filtroScoreMin = signal<number | null>(null);
  readonly pagina = signal(1);
  readonly tamanhoPagina = 25;

  // Upload
  readonly enviandoArquivo = signal(false);
  readonly arquivoSelecionado = signal<File | null>(null);

  // Detalhe
  readonly comprovanteDetalheId = signal<string | null>(null);

  readonly totalPaginas = computed(() =>
    Math.max(1, Math.ceil(this.total() / this.tamanhoPagina)),
  );
  readonly podeVoltar = computed(() => this.pagina() > 1);
  readonly podeAvancar = computed(() => this.pagina() < this.totalPaginas());

  // Stats agregados (calculados sobre lista atual)
  readonly stats = computed(() => {
    const lista = this.comprovantes();
    return {
      total: lista.length,
      analisado: lista.filter((c) => c.status === 'analisado').length,
      homologado: lista.filter((c) => c.status === 'homologado').length,
      rejeitado: lista.filter((c) => c.status === 'rejeitado').length,
      baixa_confianca: lista.filter((c) => c.score_confianca < 0.7 && c.status === 'analisado')
        .length,
    };
  });

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const res = await this.service.listar({
        status: this.filtroStatus() || undefined,
        score_minimo: this.filtroScoreMin() ?? undefined,
        page: this.pagina(),
        size: this.tamanhoPagina,
      });
      this.comprovantes.set(res.items);
      this.total.set(res.total);
    } catch (e) {
      this.erro.set('Não foi possível carregar comprovantes. Tente novamente.');
    } finally {
      this.carregando.set(false);
    }
  }

  async aplicarFiltros(): Promise<void> {
    this.pagina.set(1);
    await this.carregar();
  }

  async limparFiltros(): Promise<void> {
    this.filtroStatus.set('');
    this.filtroScoreMin.set(null);
    this.pagina.set(1);
    await this.carregar();
  }

  // ── Upload ────────────────────────────────────────────────────

  onArquivoSelecionado(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.arquivoSelecionado.set(input.files[0]);
    }
  }

  async enviar(): Promise<void> {
    const arquivo = this.arquivoSelecionado();
    if (!arquivo) return;
    this.enviandoArquivo.set(true);
    try {
      const comprovante = await this.service.analisar(arquivo);
      const score = (comprovante.score_confianca * 100).toFixed(0);
      const status_msg =
        comprovante.titulo_id !== null
          ? `Vinculado a um título (score ${score}%)`
          : 'Sem vínculo automático — atribua manualmente';
      this.toast.show({
        type: comprovante.score_confianca >= 0.7 ? 'success' : 'warning',
        message: `Comprovante analisado. ${status_msg}`,
      });
      this.arquivoSelecionado.set(null);
      // Reset input file
      const fileInput = document.getElementById('arquivo-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      await this.carregar();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro desconhecido';
      this.toast.show({ type: 'error', message: `Falha ao analisar: ${msg}` });
    } finally {
      this.enviandoArquivo.set(false);
    }
  }

  // ── Detalhe ───────────────────────────────────────────────────

  abrirDetalhe(c: Comprovante): void {
    this.comprovanteDetalheId.set(c.id);
  }

  fecharDetalhe(): void {
    this.comprovanteDetalheId.set(null);
  }

  async aposAcao(): Promise<void> {
    this.fecharDetalhe();
    await this.carregar();
  }

  // ── Helpers de UI ─────────────────────────────────────────────

  corPorScore(score: number): 'verde' | 'amarelo' | 'vermelho' {
    if (score >= 0.85) return 'verde';
    if (score >= 0.7) return 'amarelo';
    return 'vermelho';
  }

  rotuloStatus(status: StatusComprovante): string {
    const map: Record<StatusComprovante, string> = {
      analisado: 'Aguardando homologação',
      homologado: 'Homologado',
      rejeitado: 'Rejeitado',
      erro_analise: 'Erro de análise',
    };
    return map[status] ?? status;
  }

  rotuloMetodo(metodo: string | null): string {
    if (!metodo) return '—';
    const map: Record<string, string> = {
      br_code: 'QR Code PIX',
      pdf_texto: 'PDF (texto)',
      ocr: 'OCR de imagem',
      ia: 'IA Vision',
    };
    return map[metodo] ?? metodo;
  }
}

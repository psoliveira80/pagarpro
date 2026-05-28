import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe, DecimalPipe, NgClass } from '@angular/common';
import {
  Comprovante,
  ComprovantesService,
} from '../../../core/services/comprovantes.service';
import { ModalComponent } from '../../../shared/components/modal/modal.component';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { ConfirmService } from '../../../shared/services/confirm.service';

@Component({
  selector: 'app-comprovante-detalhe',
  standalone: true,
  imports: [FormsModule, NgClass, DatePipe, DecimalPipe, ModalComponent],
  templateUrl: './comprovante-detalhe.component.html',
  styleUrl: './comprovante-detalhe.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComprovanteDetalheComponent implements OnInit {
  private readonly service = inject(ComprovantesService);
  private readonly toast = inject(ToastService);
  private readonly confirmService = inject(ConfirmService);

  readonly comprovanteId = input.required<string>();
  readonly fechado = output<void>();
  readonly atualizado = output<void>();

  readonly comprovante = signal<Comprovante | null>(null);
  readonly carregando = signal(true);
  readonly processando = signal(false);
  readonly motivoRejeicao = signal('');
  readonly mostraRejeitar = signal(false);

  readonly corScore = computed(() => {
    const c = this.comprovante();
    if (!c) return 'amarelo';
    if (c.score_confianca >= 0.85) return 'verde';
    if (c.score_confianca >= 0.7) return 'amarelo';
    return 'vermelho';
  });

  readonly podeHomologar = computed(() => {
    const c = this.comprovante();
    return c?.status === 'analisado' && c.titulo_id !== null && c.valor_detectado !== null;
  });

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    try {
      const c = await this.service.detalhar(this.comprovanteId());
      this.comprovante.set(c);
    } catch {
      this.toast.show({ type: 'error', message: 'Não foi possível carregar o comprovante.' });
    } finally {
      this.carregando.set(false);
    }
  }

  fechar(): void {
    this.fechado.emit();
  }

  async homologar(): Promise<void> {
    const c = this.comprovante();
    if (!c) return;
    const ok = await this.confirmService.confirm({
      title: 'Homologar comprovante?',
      text: `Confirma o pagamento de R$ ${c.valor_detectado?.toFixed(2)} no título vinculado? Esta ação registra o pagamento e atualiza o título.`,
      type: 'info',
      confirmText: 'Sim, homologar',
    });
    if (!ok) return;

    this.processando.set(true);
    try {
      await this.service.homologar(c.id);
      this.toast.show({ type: 'success', message: 'Comprovante homologado e título atualizado.' });
      this.atualizado.emit();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao homologar';
      this.toast.show({ type: 'error', message: msg });
    } finally {
      this.processando.set(false);
    }
  }

  async rejeitar(): Promise<void> {
    const c = this.comprovante();
    if (!c) return;
    const motivo = this.motivoRejeicao().trim();
    if (motivo.length < 5) {
      this.toast.show({
        type: 'warning',
        message: 'Informe um motivo (ao menos 5 caracteres).',
      });
      return;
    }
    this.processando.set(true);
    try {
      await this.service.rejeitar(c.id, motivo);
      this.toast.show({ type: 'info', message: 'Comprovante rejeitado.' });
      this.atualizado.emit();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao rejeitar';
      this.toast.show({ type: 'error', message: msg });
    } finally {
      this.processando.set(false);
    }
  }

  rotuloMetodo(m: string | null): string {
    const map: Record<string, string> = {
      br_code: 'QR Code PIX (BR Code)',
      pdf_texto: 'Texto direto de PDF',
      ocr: 'OCR de imagem',
      ia: 'IA Vision',
    };
    return m ? (map[m] ?? m) : '—';
  }
}

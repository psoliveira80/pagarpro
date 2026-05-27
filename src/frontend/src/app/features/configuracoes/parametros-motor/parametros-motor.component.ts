import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgClass } from '@angular/common';
import {
  ConfiguracaoSistema,
  ConfiguracaoUpdate,
  ConfiguracoesService,
} from '../../../core/services/configuracoes.service';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { AuthService } from '../../../core/services/auth.service';

interface CampoVisivel extends ConfiguracaoSistema {
  rotulo: string;
  ajuda: string;
  sufixo?: string;
  prefixo?: string;
}

interface SecaoVisivel {
  id: 'financeiro' | 'frota' | 'comunicacao';
  rotulo: string;
  icone: string;
  campos: CampoVisivel[];
}

// Mapas de slug → metadata visual (rótulo PT-BR + ajuda).
// O backend não armazena rótulo/ajuda formatados — esse mapa é o glossário UI.
const METADATA: Record<string, { rotulo: string; ajuda: string; sufixo?: string; prefixo?: string }> = {
  // Financeiro
  dias_antecedencia_lembrete: {
    rotulo: 'Dias de antecedência do lembrete',
    ajuda: 'Quantos dias antes do vencimento o sistema envia mensagem de lembrete ao cliente.',
    sufixo: 'dias',
  },
  dias_carencia: {
    rotulo: 'Dias de carência',
    ajuda: 'Tolerância em dias após vencimento antes do título ser considerado em atraso.',
    sufixo: 'dias',
  },
  percentual_multa: {
    rotulo: 'Multa por atraso',
    ajuda: 'Percentual de multa aplicado sobre o valor do título quando vencido.',
    sufixo: '%',
  },
  percentual_juros_dia: {
    rotulo: 'Juros ao dia',
    ajuda: 'Percentual de juros que incide a cada dia de atraso (≈ 1% a.m. ≈ 0,0333%/dia).',
    sufixo: '% / dia',
  },
  limite_tentativas_cobranca: {
    rotulo: 'Limite de tentativas de cobrança',
    ajuda: 'Máximo de mensagens automáticas de cobrança que o sistema envia por título.',
    sufixo: 'tentativas',
  },
  intervalo_tentativas_horas: {
    rotulo: 'Intervalo entre tentativas',
    ajuda: 'Horas mínimas entre uma tentativa de cobrança e a próxima.',
    sufixo: 'h',
  },
  limite_dias_suspensao: {
    rotulo: 'Dias para suspensão automática',
    ajuda: 'Dias de atraso após os quais o contrato é suspenso (veículo é bloqueado).',
    sufixo: 'dias',
  },
  limite_dias_encerramento: {
    rotulo: 'Dias para encerrar com pendência',
    ajuda: 'Atraso máximo antes do contrato ser encerrado mantendo a dívida ativa.',
    sufixo: 'dias',
  },
  permite_pagamento_parcial: {
    rotulo: 'Aceitar pagamentos parciais',
    ajuda: 'Quando ativo, pagamentos abaixo do valor total abatem proporcionalmente.',
  },
  limite_fusao_parcial_pct: {
    rotulo: 'Percentual mínimo de pagamento parcial',
    ajuda: 'Pagamento abaixo desse % do valor da parcela funde o restante na próxima.',
    sufixo: '%',
  },
  // Frota
  desbloqueio_confianca_dias: {
    rotulo: 'Validade do desbloqueio em confiança',
    ajuda: 'Por quantos dias o desbloqueio temporário fica ativo até nova verificação.',
    sufixo: 'dias',
  },
  desbloqueio_confianca_min_meses_historico: {
    rotulo: 'Histórico mínimo para confiança',
    ajuda: 'Meses de relacionamento necessários para o cliente ser elegível ao desbloqueio em confiança.',
    sufixo: 'meses',
  },
  desbloqueio_confianca_max_atrasos_historico: {
    rotulo: 'Máximo de atrasos no histórico',
    ajuda: 'Quantidade máxima de atrasos passados que ainda permite desbloqueio em confiança.',
    sufixo: 'ocorrências',
  },
  // Comunicação
  canal_cobranca_principal: {
    rotulo: 'Canal de cobrança principal',
    ajuda: 'Canal padrão usado nas tentativas de cobrança automática.',
  },
  canal_cobranca_fallback: {
    rotulo: 'Canal de cobrança fallback',
    ajuda: 'Canal alternativo quando o principal falha (vazio = sem fallback).',
  },
};

const ROTULOS_SECAO: Record<SecaoVisivel['id'], { rotulo: string; icone: string }> = {
  financeiro: { rotulo: 'Financeiro', icone: '💰' },
  frota: { rotulo: 'Frota', icone: '🚗' },
  comunicacao: { rotulo: 'Comunicação', icone: '💬' },
};

@Component({
  selector: 'app-parametros-motor',
  standalone: true,
  imports: [FormsModule, NgClass],
  templateUrl: './parametros-motor.component.html',
  styleUrl: './parametros-motor.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ParametrosMotorComponent implements OnInit {
  private readonly service = inject(ConfiguracoesService);
  private readonly toast = inject(ToastService);
  private readonly auth = inject(AuthService);

  readonly carregando = signal(true);
  readonly erro = signal<string | null>(null);
  readonly configuracoes = signal<ConfiguracaoSistema[]>([]);

  readonly secaoAtiva = signal<SecaoVisivel['id']>('financeiro');

  // Timestamp do último save por slug — usado pelo "✓ Salvo às HH:mm:ss"
  readonly ultimosSaves = signal<Record<string, string>>({});

  // Estado de erro de validação por slug — usado para feedback inline
  readonly errosPorSlug = signal<Record<string, string | null>>({});

  // Debounce timers por slug
  private readonly timers = new Map<string, ReturnType<typeof setTimeout>>();
  private readonly DEBOUNCE_MS = 1000;

  readonly secoes = computed<SecaoVisivel[]>(() => {
    const configs = this.configuracoes();
    const result: SecaoVisivel[] = (['financeiro', 'frota', 'comunicacao'] as const).map((id) => ({
      id,
      rotulo: ROTULOS_SECAO[id].rotulo,
      icone: ROTULOS_SECAO[id].icone,
      campos: configs
        .filter((c) => c.modulo === id)
        .map((c) => ({
          ...c,
          rotulo: METADATA[c.slug]?.rotulo ?? c.slug,
          ajuda: METADATA[c.slug]?.ajuda ?? c.descricao ?? 'Sem descrição',
          sufixo: METADATA[c.slug]?.sufixo,
          prefixo: METADATA[c.slug]?.prefixo,
        })),
    }));
    return result;
  });

  readonly isAdmin = computed(() => {
    const user = this.auth.currentUser();
    if (!user) return false;
    const roles = (user.roles ?? []).map((r) => r.toLowerCase());
    return roles.includes('admin');
  });

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const lista = await this.service.listar();
      this.configuracoes.set(lista);
    } catch (e) {
      this.erro.set('Não foi possível carregar configurações. Tente novamente.');
    } finally {
      this.carregando.set(false);
    }
  }

  selecionarSecao(id: SecaoVisivel['id']): void {
    this.secaoAtiva.set(id);
  }

  // Conversão e validação de valor antes de mandar pro backend
  private converterValor(campo: CampoVisivel, raw: string | boolean): unknown {
    if (campo.tipo_valor === 'inteiro') {
      const n = parseInt(String(raw), 10);
      if (Number.isNaN(n)) throw new Error('Valor inteiro inválido');
      return n;
    }
    if (campo.tipo_valor === 'decimal') {
      const n = parseFloat(String(raw).replace(',', '.'));
      if (Number.isNaN(n)) throw new Error('Valor decimal inválido');
      return n;
    }
    if (campo.tipo_valor === 'booleano') {
      return !!raw;
    }
    return raw;
  }

  // Handler genérico de mudança com debounce
  onValorAlterado(campo: CampoVisivel, novoValor: string | boolean): void {
    if (!this.isAdmin()) return;

    // Atualiza o array em memória imediatamente para refletir na UI
    const lista = this.configuracoes().map((c) =>
      c.slug === campo.slug ? { ...c, valor: String(novoValor) } : c,
    );
    this.configuracoes.set(lista);

    // Limpa erro anterior
    this.errosPorSlug.update((errs) => ({ ...errs, [campo.slug]: null }));

    // Debounce do save
    const existing = this.timers.get(campo.slug);
    if (existing) clearTimeout(existing);
    const t = setTimeout(() => this.persistir(campo, novoValor), this.DEBOUNCE_MS);
    this.timers.set(campo.slug, t);
  }

  private async persistir(campo: CampoVisivel, novoValor: string | boolean): Promise<void> {
    try {
      const valor = this.converterValor(campo, novoValor);
      const update: ConfiguracaoUpdate = {
        valor: valor as ConfiguracaoUpdate['valor'],
        tipo_valor: campo.tipo_valor,
        modulo: campo.modulo,
      };
      await this.service.atualizar(campo.slug, update);
      const agora = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      this.ultimosSaves.update((s) => ({ ...s, [campo.slug]: agora }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erro ao salvar';
      this.errosPorSlug.update((errs) => ({ ...errs, [campo.slug]: msg }));
      this.toast.show({ type: 'error', message: `Falha ao salvar "${campo.rotulo}": ${msg}` });
    }
  }
}

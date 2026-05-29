import { Routes } from '@angular/router';

export const CONFIGURACOES_ROUTES: Routes = [
  {
    path: 'parametros',
    loadComponent: () =>
      import('./parametros-motor/parametros-motor.component').then((m) => m.ParametrosMotorComponent),
  },
  {
    path: 'agente',
    loadComponent: () =>
      import('./agente-config/agente-config.component').then((m) => m.AgenteConfigComponent),
  },
  {
    path: 'usuarios',
    loadComponent: () =>
      import('./configuracoes-placeholder/configuracoes-placeholder.component').then((m) => m.ConfiguracoesPlaceholderComponent),
  },
  {
    path: 'papeis',
    loadComponent: () =>
      import('./configuracoes-placeholder/configuracoes-placeholder.component').then((m) => m.ConfiguracoesPlaceholderComponent),
  },
  {
    path: 'financeiro',
    loadComponent: () =>
      import('./financeiro-configuracoes/financeiro-configuracoes.component').then((m) => m.FinanceiroConfiguracoesComponent),
  },
  {
    path: 'contratos',
    loadComponent: () =>
      import('./contrato-configuracoes/contrato-configuracoes.component').then((m) => m.ContratoConfiguracoesComponent),
  },
  {
    path: 'geral',
    loadComponent: () =>
      import('./integracoes/integracoes.component').then((m) => m.IntegracoesComponent),
  },
  {
    path: 'integracoes',
    loadComponent: () =>
      import('./integracoes/integracoes.component').then((m) => m.IntegracoesComponent),
  },
  {
    path: 'canais/whatsapp',
    loadComponent: () =>
      import('./canais-whatsapp/canais-whatsapp.component').then((m) => m.CanaisWhatsappComponent),
  },
  {
    path: 'log-auditoria',
    loadComponent: () =>
      import('./log-auditoria/log-auditoria.component').then((m) => m.LogAuditoriaComponent),
  },
  {
    path: 'modulos',
    loadComponent: () =>
      import('./modulos/modulos.component').then((m) => m.ModulosComponent),
  },
];

import { Routes } from '@angular/router';
import { SistemaComponent } from './sistema.component';

export const SYSTEM_ROUTES: Routes = [
  {
    path: '',
    component: SistemaComponent,
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('../dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'clientes',
        loadChildren: () =>
          import('../clientes/clientes.routes').then((m) => m.CLIENTES_ROUTES),
      },
      {
        path: 'veiculos',
        loadChildren: () =>
          import('../veiculos/veiculos.routes').then((m) => m.VEICULOS_ROUTES),
      },
      {
        path: 'contratos',
        loadChildren: () =>
          import('../contratos/contratos.routes').then((m) => m.CONTRATOS_ROUTES),
      },
      {
        path: 'financeiro',
        loadChildren: () =>
          import('../financeiro/financeiro.routes').then((m) => m.FINANCEIRO_ROUTES),
      },
      {
        path: 'configuracoes',
        loadChildren: () =>
          import('../configuracoes/configuracoes.routes').then((m) => m.CONFIGURACOES_ROUTES),
      },
      {
        path: 'inbox',
        loadComponent: () =>
          import('../inbox/whatsapp-inbox/whatsapp-inbox.component').then((m) => m.WhatsappInboxComponent),
      },
      {
        path: 'inbox/avisos',
        loadComponent: () =>
          import('../inbox/avisos-lista/avisos-lista.component').then((m) => m.AvisosListaComponent),
      },
      {
        path: 'relatorios',
        loadComponent: () =>
          import('../relatorios/relatorios-lista/relatorios-lista.component').then((m) => m.RelatoriosListaComponent),
      },
      {
        path: 'relatorios/builder',
        loadComponent: () =>
          import('../relatorios/relatorio-builder/relatorio-builder.component').then((m) => m.RelatorioBuilderComponent),
      },
      {
        path: 'relatorios/:type',
        loadComponent: () =>
          import('../relatorios/relatorio-viewer/relatorio-viewer.component').then((m) => m.RelatorioViewerComponent),
      },
      {
        path: 'perfil',
        loadComponent: () =>
          import('../configuracoes/configuracoes-placeholder/configuracoes-placeholder.component').then((m) => m.ConfiguracoesPlaceholderComponent),
      },
      {
        path: 'preferencias',
        loadComponent: () =>
          import('../configuracoes/configuracoes-placeholder/configuracoes-placeholder.component').then((m) => m.ConfiguracoesPlaceholderComponent),
      },
      {
        path: 'seguranca',
        loadComponent: () =>
          import('../configuracoes/configuracoes-placeholder/configuracoes-placeholder.component').then((m) => m.ConfiguracoesPlaceholderComponent),
      },
    ],
  },
];

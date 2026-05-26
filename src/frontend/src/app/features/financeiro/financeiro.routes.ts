import { Routes } from '@angular/router';

export const FINANCEIRO_ROUTES: Routes = [
  {
    path: 'titulos-receber',
    loadComponent: () =>
      import('./titulos-receber-lista/titulos-receber-lista.component').then((m) => m.TitulosReceberListaComponent),
  },
  {
    path: 'fila-validacao',
    loadComponent: () =>
      import('./fila-validacao/fila-validacao.component').then((m) => m.FilaValidacaoComponent),
  },
  {
    path: 'titulos-pagar',
    loadComponent: () =>
      import('./titulos-pagar-lista/titulos-pagar-lista.component').then((m) => m.TitulosPagarListaComponent),
  },
  {
    path: 'despesas-recorrentes',
    loadComponent: () =>
      import('./despesas-recorrentes/despesas-recorrentes.component').then((m) => m.DespesasRecorrentesComponent),
  },
  {
    path: 'dre',
    loadComponent: () =>
      import('./dre-relatorio/dre-relatorio.component').then((m) => m.DreRelatorioComponent),
  },
  {
    path: 'contas-bancarias',
    loadComponent: () =>
      import('./contas-bancarias-lista/contas-bancarias-lista.component').then((m) => m.ContasBancariasListaComponent),
  },
  {
    path: 'importacao-bancaria',
    loadComponent: () =>
      import('./importacao-bancaria/importacao-bancaria.component').then((m) => m.ImportacaoBancariaComponent),
  },
  {
    path: 'conciliacao',
    loadComponent: () =>
      import('./conciliacao/conciliacao.component').then((m) => m.ConciliacaoComponent),
  },
  {
    path: 'divergencias',
    loadComponent: () =>
      import('./divergencias/divergencias.component').then((m) => m.DivergenciasComponent),
  },
];

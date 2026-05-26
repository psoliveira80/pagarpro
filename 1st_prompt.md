É o seguinte, um amigo meu tem uma frota de carros alugados para uber. Ele controla tudo via planilha de excel. Ele disse que o que mais dá trabalho é ter que ficar cobrando os motoristas das parcelas. Eu quero desenvolver um app para que ele possa: 

cadastrar clientes e os veiculos (modelo, marca, ano, km, valor de compra etc). Podemos automaticamente puxar o preço da tabela fipe da frota para saber quanto está valendo a frota inteira. Ele tem um sistema de rastreamento, podemos tentar conectar na api do aparelho e de repente localizar os carros num mapa. Gerar os contratos com as parcelas e o acordo de forma personalizada). Usuario pode rever e refazer o contrato, editando as parcelas em aberto em  lote. Gerar relatórios e dashboards financeiros para cada cliente. Seria interessante se o cliente quiser incluir a forma de pagametno da aquisição do veiculo, com juros, carencia etc, para que possa fazer um comparativo com os lucros recebidos, somando com o valor do bem e a depreciação.

Registrar os modelos de pagamento individuais de cada motorista, gerando titulos a serem pagos para cada um deles e baixados mediante envio de comprovante (nesse caso temos de ter um agente que valida o comprovante enviado). Seria interessante se pudesse conectar uma api como a asaas que gera um codigo e envia um webhook assim que é pago, baixando o titulo automaticamente. O problema é que custa 2,00 por pix e ele disse que nao esta disposto a pagar, pois faz mais de 100 pix por mes. Entao por padrao iremos verificar o comprovante e dar uma baixa no titulo mas que fica com status de pendente de verificacao ou conciliação bancária (para ter certeza que caiu na conta). Entao esse seria o modulo do contas a receber.  Teriamos tbm um modulo de contas a pagar, voce ja deve conhecer um modelo padrão para isso. Despesas recorrentes o sistema gera todo mes. Se for lançar um pagamento ja lança o titulo e da baixa ao mesmo tempo, essas coisas. 

NA parte de cobranças haverá uma integração com uma api de whatsapp e um agente treinado com rag e talvez com mcp que acessa o historico do individuo. O agente deve fazer as cobranças em tom natural, sempre enviar o card padrão do pix do whatsapp e ao receber o comprovante, o agente deve estar preparado para enviar para validação, com uma especie de baixa primária (que vai ainda aguardar confirmacao). O agente deve ser capaz de conversar amigavelmente, se for um cliente com boa nota pode dar uns dias a mais apos o vencimento, e se nao for ele pode ate invocar a api de bloqueio do carro via rastreador. É importante parametrizar tudo isso (juros por atraso, notas que permitem concessao de dias a mais, numero maximo de dias, enfim, tudo deve ser parametrizado). Guardar o histórico de chat do whatsapp para que o gerente possa acompanhar as conversas, o chat deve ter a aparencia parecida com o whsatsapp.

Conciliação bancária: tela de conciliação bancária sofisticada, com recursos de arrastar e soltar quando couber. Cliques para confirmar os pagamentos. Devemos facilitar ao máximo a vida do usuário. Possibilidade de importação de arquivos fornecidos pelos bancos, como OFX. Mas também a possibilidade de o usuário importar um extrato em pdf, e o sistema fazer a leitura inteligente, buscando conciliar os valores pelas datas, e outras informações mais.

plug and play: é importante que o sistema possa ser construido desacoplado das ferramentas, para que numa eventual substituicao fique mais facil para o desenvolvedor.

Dashboard principal, tela de relatórios (por exemplo os carros/clientes que mais venderam), a km percorrida (caso a api forneça), o retorno financeiro em percentual de cada carro (aquisição x retorno).

Enfim, acho que deu para você entender? Usaremos o método bmad. Dessa forma gostaria que fizesse um prd em cima dessas informações e também a seguinte architecture: 

backend vai rodar em python com fastapi. caso precise de atualizações do backend para o frontend, decidir qual abordagem seria melhor, se via polling, see ou websocket.

frontend com angular 21+, com predominância maxima do uso de signals e resources nativos (seguir rules anexadas para a criação de arquivos e pastas e ux); 

Impressione:
Use componentes sofisticados  para impressionar o usuário. O frontend deve cobrir completamente todas as funções citadas. Quando couber, use componentes de arrastar e soltar. 


Flexibilidade: 
Por exemplo, o usuario vai querer informar a forma de pagamento que ele fez pra adquirir o veiculo, e existem N formas para isso, entao crie telas que entregue todas as possibilidades (entrada + N parcelas + semestrais etc etc etc). Sempre com possibilidades de rollback  para titulos em aberto. Os titulos ja baixados sao imutaveis.


Pesquise, avalie, complemente, resolva.. 
Gere o PRD e Architecture em formato md, com o maximo de detalhes possivel, para que eu jogue no meu cli.
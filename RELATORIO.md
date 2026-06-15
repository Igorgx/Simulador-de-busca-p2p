# Relatório do Simulador de Busca em Redes P2P

## 1. Objetivo do sistema

Este projeto implementa um simulador de busca de recursos em uma rede P2P não estruturada. A rede é formada por nós conectados por relações de vizinhança. Cada nó possui um identificador, conhece seus vizinhos e mantém uma lista de recursos locais.

O sistema permite executar buscas por recursos usando quatro algoritmos:

- `flooding`
- `informed_flooding`
- `random_walk`
- `informed_random_walk`

Além da execução textual pelo terminal, o sistema possui uma interface visual no navegador para demonstrar o funcionamento passo a passo, permitindo que o professor escolha o nó de origem, o recurso, o TTL e o algoritmo durante a apresentação.

## 2. Organização principal do código

Os principais arquivos do projeto são:

- `main.py`: ponto de entrada da aplicação.
- `p2p_simulator/config.py`: leitura e normalização do arquivo de configuração.
- `p2p_simulator/models.py`: estruturas de dados da rede, nó, eventos e resultado da busca.
- `p2p_simulator/search.py`: implementação dos algoritmos de busca.
- `p2p_simulator/demo_server.py`: interface visual passo a passo no navegador.
- `p2p_simulator/visualize.py`: geração de imagens, GIFs e gráficos.
- `configs/sample.yaml`: topologia principal usada na demonstração.
- `tests/test_simulator.py`: testes automatizados.

## 3. Arquivo de entrada da rede

O trabalho pede que o programa receba uma configuração com o seguinte formato ou equivalente em JSON/YAML:

```yaml
num_nodes: 12
min_neighbors: 2
max_neighbors: 4
resources:
  n1: [r1, r2]
  n2: [r3, r4]
edges:
  - [n1, n2]
  - [n1, n3]
```

O projeto usa YAML por ser legível e simples de editar. O arquivo principal é `configs/sample.yaml`.

Na configuração atual:

- existem 12 nós;
- o mínimo de vizinhos é 2;
- o máximo de vizinhos é 4;
- existem 24 recursos distintos, de `r1` até `r24`;
- cada nó possui dois recursos;
- a topologia não é particionada.

Distribuição atual dos recursos:

```yaml
n1: [r1, r2]
n2: [r3, r4]
n3: [r5, r6]
n4: [r7, r8]
n5: [r9, r10]
n6: [r12, r13]
n7: [r14, r15]
n8: [r16, r17]
n9: [r18, r19]
n10: [r11, r20]
n11: [r21, r22]
n12: [r23, r24]
```

O recurso `r11` foi mantido em `n10` porque é usado nos exemplos de demonstração.

## 4. Atendimento aos requisitos do PDF

### 4.1 Leitura do arquivo de configuração

Requisito:

> O programa deverá receber como entrada um arquivo de configuração contendo número de nós, limites de vizinhos, recursos e arestas.

Como foi atendido:

- A função `load_config` em `p2p_simulator/config.py` lê arquivos YAML ou JSON.
- A função `network_from_dict` extrai:
  - `num_nodes`;
  - `min_neighbors`;
  - `max_neighbors`;
  - `resources`;
  - `edges`.
- Os nós são criados automaticamente como `n1`, `n2`, ..., `nN`, de acordo com `num_nodes`.

O sistema aceita recursos em formato de lista YAML:

```yaml
n1: [r1, r2]
```

E também aceita formato textual separado por vírgula:

```yaml
n1: r1, r2
```

As arestas também podem ser escritas como lista:

```yaml
- [n1, n2]
```

Ou como texto:

```yaml
- n1, n2
```

### 4.2 Verificação de rede não particionada

Requisito:

> A rede não pode estar particionada, ou seja, deve existir pelo menos um caminho conectando qualquer nó a qualquer outro nó.

Como foi atendido:

- A validação é feita em `P2PNetwork.validate`, no arquivo `p2p_simulator/models.py`.
- O método `_validate_connected` percorre a rede a partir de um nó inicial usando busca em profundidade.
- Se algum nó não for alcançado, o sistema rejeita a configuração e informa quais nós ficaram inalcançáveis.

Com isso, o programa garante que todos os nós pertencem ao mesmo componente conectado.

### 4.3 Verificação de mínimo e máximo de vizinhos

Requisito:

> Os números mínimo e máximo de vizinhos de cada nó devem obedecer os limites estabelecidos nos parâmetros `min_neighbors` e `max_neighbors`.

Como foi atendido:

- Durante a validação, o sistema calcula o grau de cada nó, ou seja, quantos vizinhos ele possui.
- Se algum nó tiver menos vizinhos que `min_neighbors` ou mais vizinhos que `max_neighbors`, a configuração é recusada.

Na topologia principal:

- `min_neighbors = 2`
- `max_neighbors = 4`
- a validação informa grau mínimo/máximo/médio da rede.

Comando:

```bash
python main.py validate configs/sample.yaml
```

Saída esperada:

```text
Configuração válida.
Nós: 12
Recursos distintos: 24
Grau mínimo/máximo/médio: 3/4/3.17
```

### 4.4 Verificação de nós sem recursos

Requisito:

> Não pode haver nós sem recursos.

Como foi atendido:

- Cada objeto `Node` possui um conjunto `resources`.
- Durante a validação, se `resources` estiver vazio, a configuração é recusada.

Na topologia principal, todos os 12 nós possuem exatamente dois recursos.

### 4.5 Verificação de arestas para o próprio nó

Requisito:

> Não pode haver arestas de um nó para ele mesmo.

Como foi atendido:

- Na leitura da configuração, se uma aresta tiver origem e destino iguais, o sistema gera erro.
- A validação da rede também verifica se algum nó aparece como vizinho de si mesmo.

Exemplo inválido:

```yaml
edges:
  - [n1, n1]
```

Esse caso é rejeitado.

## 5. Atendimento aos requisitos de busca

### 5.1 Parâmetros de cada busca

Requisito:

> Cada operação de busca deve receber `node_id`, `resource_id`, `ttl` e `algo`.

Como foi atendido:

Pela CLI, o comando é:

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

Correspondência com o enunciado:

| Enunciado | Implementação |
|---|---|
| `node_id` | `--origin` |
| `resource_id` | `--resource` |
| `ttl` | `--ttl` |
| `algo` | `--algo` |

Na interface visual, os mesmos parâmetros aparecem como controles:

- Nó de origem;
- Recurso procurado;
- Algoritmo;
- TTL.

### 5.2 Algoritmos disponíveis

Requisito:

> Os valores possíveis para `algo` são `flooding`, `informed_flooding`, `random_walk`, `informed_random_walk`.

Como foi atendido:

Os quatro algoritmos estão registrados em `p2p_simulator/search.py`:

```python
ALGORITHMS = {
    "flooding",
    "informed_flooding",
    "random_walk",
    "informed_random_walk",
}
```

Se o usuário tentar passar um algoritmo inválido, o sistema rejeita a busca.

### 5.3 Busca por inundação

Funcionamento:

- O nó de origem envia a busca para todos os seus vizinhos.
- Cada vizinho que recebe a busca verifica se possui o recurso.
- Se não possuir, retransmite para seus vizinhos enquanto houver TTL.
- Duplicatas são ignoradas para evitar processamento repetido.
- Quando o recurso é encontrado, a resposta volta pelo caminho inverso.

Esse algoritmo tende a encontrar o recurso com maior probabilidade, mas gera mais mensagens.

### 5.4 Busca por passeio aleatório

Funcionamento:

- O nó atual escolhe apenas um vizinho aleatoriamente.
- A busca segue por esse vizinho.
- O processo se repete até encontrar o recurso ou o TTL acabar.

Esse algoritmo gera menos mensagens que o flooding, mas pode falhar dependendo do caminho escolhido.

### 5.5 Busca informada com cache

Funcionamento:

- Nas versões `informed_flooding` e `informed_random_walk`, cada nó consulta seu cache antes de continuar a busca.
- Se o nó já souber onde está o recurso, a busca pode terminar sem precisar chegar ao nó dono.
- Quando um recurso é encontrado, os nós do caminho aprendem a localização e salvam no cache.

Exemplo:

```text
r11 -> n10
```

Isso significa que algum nó aprendeu que o recurso `r11` está no nó `n10`.

## 6. Requisitos passados oralmente/em texto

### 6.1 Cada nó sabe seu ID

Como foi atendido:

- Cada nó é representado por um objeto `Node`.
- O campo `node_id` armazena o identificador do nó, como `n1`, `n2`, `n3`.

### 6.2 Cada nó sabe quem são seus vizinhos

Como foi atendido:

- Cada nó possui o campo `neighbors`.
- Esse campo guarda apenas os IDs dos nós diretamente conectados.

Exemplo:

```yaml
edges:
  - [n1, n2]
  - [n1, n3]
```

Isso faz `n1` conhecer `n2` e `n3` como vizinhos.

### 6.3 Cada nó tem uma lista de recursos locais

Como foi atendido:

- Cada nó possui o campo `resources`.
- Na topologia principal, cada nó possui dois recursos.

Exemplo:

```yaml
n10: [r11, r20]
```

Somente o nó `n10` possui localmente os recursos `r11` e `r20`.

### 6.4 Só quem sabe seus recursos é o próprio nó

Como foi atendido:

- No início da simulação, o recurso local fica armazenado apenas no próprio nó.
- A busca precisa percorrer a rede para descobrir onde o recurso está.
- Outros nós só passam a conhecer a localização depois que essa informação chega até eles por uma busca concluída, por meio do cache.

### 6.5 Pode pedir o recurso direto de um nó para outro distante

Como foi atendido:

- A relação de vizinhança é usada para descobrir onde o recurso está.
- Depois que a origem descobre qual nó possui o recurso, o sistema representa uma transferência direta.
- Essa transferência direta aparece na visualização como uma linha roxa tracejada.

Exemplo:

```text
n1 solicita r11 diretamente a n10
n10 envia r11 diretamente para n1
```

Isso demonstra que a vizinhança não limita a transferência final do recurso. Ela serve para a descoberta.

### 6.6 A relação de vizinhança é para descobrir onde o recurso está

Como foi atendido:

- Todas as mensagens de busca seguem as arestas da rede.
- A busca só pode ser retransmitida para vizinhos.
- Depois que a localização é descoberta, o pedido direto não precisa seguir a topologia.

Na interface:

- linhas vermelhas representam mensagens de busca entre vizinhos;
- linhas verdes representam o aviso voltando pelo caminho;
- linha roxa tracejada representa o pedido direto do recurso.

### 6.7 Implementar TTL

Como foi atendido:

- Toda busca recebe um valor de TTL.
- A cada salto, o TTL é decrementado.
- Quando o TTL chega a zero, a busca não é mais retransmitida.

Na interface visual, o TTL atual aparece nos cartões de estatística e também no rastro de eventos.

### 6.8 Toda busca tem um ID

Como foi atendido:

- Cada busca recebe um identificador único, gerado automaticamente.
- Esse ID aparece:
  - no terminal;
  - na interface visual;
  - nos eventos da busca;
  - no CSV de comparação.

Exemplo:

```text
Busca: 28585969
```

### 6.9 Estatísticas da busca

Como foi atendido:

Ao final de cada busca, o sistema informa:

- se encontrou ou não o recurso;
- nó que possui o recurso;
- número de mensagens;
- número de nós envolvidos;
- cache hits;
- caminho do aviso de retorno;
- mensagens adicionais da transferência direta, quando ativada.

No terminal:

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

Na interface visual, as estatísticas aparecem em cartões:

- ID da busca;
- Status;
- Mensagens;
- Nós buscados;
- TTL atual;
- Cache hits.

### 6.10 Rastro visual ou escrito

Como foi atendido:

O sistema possui os dois tipos de rastro.

Rastro escrito:

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

Rastro visual:

```bash
python main.py demo configs/sample.yaml
```

Na interface visual, o professor pode controlar:

- próximo passo;
- passo anterior;
- play/pause;
- barra de progresso.

Cada passo mostra:

- qual nó está ativo;
- qual mensagem foi enviada;
- TTL restante;
- caminho percorrido;
- mensagens acumuladas;
- nós já buscados.

### 6.11 Cache no caminho

Como foi atendido:

- Quando uma busca encontra o recurso, os nós do caminho aprendem onde ele está.
- Essa informação é salva no cache local dos nós do caminho.
- Em buscas futuras informadas, um nó intermediário pode responder usando o cache.

Isso atende ao requisito:

> com cache algum nó no caminho sabe onde está o recurso.

### 6.12 Simulador com random walk e flooding

Como foi atendido:

O sistema implementa:

- `flooding`;
- `random_walk`;
- `informed_flooding`;
- `informed_random_walk`.

Esses algoritmos podem ser escolhidos pelo terminal ou pela interface visual.

### 6.13 Número máximo e mínimo depois de usar um algoritmo

Como foi atendido:

Existem duas formas de ver mínimo e máximo.

Pela interface visual:

```bash
python main.py demo configs/sample.yaml
```

Depois:

1. selecione o recurso;
2. selecione o TTL;
3. clique em **Calcular min/máx do recurso**.

A tabela mostra, para cada algoritmo:

- mensagens mínimas e máximas;
- nós mínimos e máximos;
- quantidade de sucessos.

Pelo terminal:

```bash
python main.py compare configs/sample.yaml --runs 40 --ttl 4
```

O comando gera:

- resumo no terminal;
- `output/comparacao.csv`;
- `output/comparacao.png`.

## 7. Interface visual de demonstração

A interface visual foi criada para responder diretamente ao que o professor pode pedir durante a apresentação.

Comando:

```bash
python main.py demo configs/sample.yaml
```

Endereço:

```text
http://127.0.0.1:8000
```

Controles disponíveis:

- seleção do nó de origem;
- seleção do recurso;
- seleção do algoritmo;
- valor de TTL;
- seed do random walk;
- opção de mostrar pedido direto;
- botão executar busca;
- botão limpar cache;
- botão calcular min/máx;
- botões próximo, anterior e play/pause.

Elementos visuais:

- azul claro: nó de origem;
- laranja: nó ativo no passo atual;
- amarelo: nó já buscado;
- verde claro: nó que possui o recurso;
- linha vermelha: mensagem de busca;
- linha verde: aviso de retorno;
- linha roxa tracejada: pedido direto do recurso.

## 8. Sobre a seed do random walk

A seed controla a sequência aleatória usada pelo `random_walk`.

O random walk escolhe um vizinho aleatoriamente. Portanto, se a busca for executada várias vezes, ela pode seguir caminhos diferentes. A seed permite repetir o mesmo sorteio.

Isso é útil para apresentação porque:

- torna a demonstração reprodutível;
- permite repetir o mesmo caminho caso o professor peça;
- facilita comparar resultados.

O valor da seed não tem significado especial. O padrão `42` poderia ser substituído por `1`, `10`, `1234` etc. O importante é que a mesma seed gera a mesma sequência de escolhas aleatórias.

## 9. Comandos principais

### Instalar dependências

```bash
python -m pip install -r requirements.txt
```

### Validar a topologia

```bash
python main.py validate configs/sample.yaml
```

### Abrir a interface visual

```bash
python main.py demo configs/sample.yaml
```

### Executar uma busca textual com rastro

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

### Executar random walk textual

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo random_walk --seed 42 --trace
```

### Executar busca informada

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo informed_flooding --trace
```

### Gerar imagem final da busca

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --plot output/flooding.png
```

### Gerar animação GIF

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo informed_flooding --animate output/busca.gif
```

### Comparar algoritmos

```bash
python main.py compare configs/sample.yaml --runs 40 --ttl 4 --csv output/comparacao.csv --chart output/comparacao.png
```

### Rodar testes automatizados

```bash
python -m pytest -q
```

## 10. Roteiro sugerido para apresentação

1. Abrir o terminal na pasta do projeto.
2. Validar a topologia:

```bash
python main.py validate configs/sample.yaml
```

3. Abrir a interface visual:

```bash
python main.py demo configs/sample.yaml
```

4. Pedir ao professor para escolher:
   - nó de origem;
   - recurso;
   - TTL;
   - algoritmo.

5. Clicar em **Executar busca**.
6. Usar **Próximo** para mostrar cada mensagem.
7. Explicar:
   - busca seguindo vizinhos;
   - decremento do TTL;
   - nó ativo;
   - mensagens enviadas;
   - nós buscados;
   - caminho de retorno.

8. Mostrar o campo **Caminho para receber o recurso**.
9. Mostrar a linha roxa tracejada do pedido direto.
10. Clicar em **Calcular min/máx do recurso** para comparar os algoritmos.
11. Trocar o algoritmo para `random_walk` e mostrar que ele usa menos mensagens, mas pode falhar dependendo do caminho e do TTL.
12. Trocar para uma versão informada e explicar o cache.

## 11. Conclusão

O sistema atende aos requisitos do trabalho porque:

- lê uma rede P2P a partir de arquivo YAML/JSON;
- valida conectividade, grau mínimo/máximo, recursos por nó e autoarestas;
- representa cada nó com ID, vizinhos, recursos locais e cache;
- implementa TTL;
- gera ID para cada busca;
- implementa flooding, random walk e versões informadas;
- registra mensagens e nós envolvidos;
- mostra rastro textual e visual;
- permite transferência direta após descobrir o nó dono;
- calcula mínimo e máximo por algoritmo;
- fornece uma interface visual controlável para apresentação ao vivo.

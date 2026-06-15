# Simulador de Busca em Redes P2P

Projeto em Python para simular buscas por recursos em redes P2P não estruturadas.

O foco da demonstração é permitir que o professor escolha, ao vivo, um nó de origem e um recurso. O sistema mostra visualmente o algoritmo funcionando passo a passo, com quantidade de mensagens, nós buscados, caminho de retorno e comparação de mínimo/máximo por algoritmo.

## Funcionalidades

- Leitura de topologias em YAML ou JSON.
- Validação da rede:
  - rede conectada;
  - grau mínimo e máximo por nó;
  - todos os nós com pelo menos um recurso;
  - sem arestas de um nó para ele mesmo.
- Cada nó conhece apenas seu ID, seus vizinhos, seus recursos locais e seu cache.
- Algoritmos:
  - `flooding`;
  - `random_walk`;
  - `informed_flooding`;
  - `informed_random_walk`.
- TTL em todas as buscas.
- ID único em cada busca.
- Estatísticas:
  - mensagens enviadas;
  - nós buscados;
  - cache hits;
  - caminho usado para avisar a origem;
  - pedido direto do recurso após descobrir o nó dono.
- Interface visual controlável:
  - botão anterior/próximo;
  - botão play/pause;
  - barra de progresso;
  - rastro escrito;
  - grafo colorido em tempo real.
- Comparação min/máx por algoritmo para o recurso escolhido.

## Instalação

```bash
python -m pip install -r requirements.txt
```

## Melhor forma de apresentar

Execute:

```bash
python main.py demo configs/sample.yaml
```

O navegador abrirá uma interface local. Se não abrir sozinho, acesse:

```text
http://127.0.0.1:8000
```

Na tela:

1. Escolha o nó de origem.
2. Escolha o recurso que o professor pedir.
3. Escolha o algoritmo.
4. Ajuste o TTL.
5. Clique em **Executar busca**.
6. Use **Próximo**, **Anterior** ou **Play** para mostrar a busca mensagem por mensagem.
7. Mostre os cartões de estatísticas:
   - ID da busca;
   - status;
   - mensagens;
   - nós buscados;
   - TTL atual;
   - cache hits.
8. Mostre o campo **Caminho para receber o recurso**.
9. Clique em **Calcular min/máx do recurso** para comparar os algoritmos.

## Cores da visualização

- Azul: nó de origem.
- Laranja: nó ativo no passo atual.
- Amarelo: nó já buscado.
- Verde: nó onde o recurso foi encontrado.
- Linha vermelha: mensagem de busca.
- Linha verde: aviso voltando para a origem.
- Linha roxa tracejada: pedido direto do recurso ao nó distante.

## Roteiro curto para explicar ao professor

> Cada nó sabe apenas seu ID, seus vizinhos e seus recursos locais. A busca usa os vizinhos para descobrir onde o recurso está. Quando o recurso é encontrado, a resposta volta pelo caminho inverso até a origem. Os nós do caminho aprendem essa localização em cache. Depois disso, a origem pode pedir o recurso diretamente ao nó dono.

## Outros comandos

Validar a configuração:

```bash
python main.py validate configs/sample.yaml
```

Executar uma busca textual:

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

Gerar imagem e GIF:

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo informed_flooding --trace --plot output/busca.png --animate output/busca.gif
```

Comparar algoritmos por várias buscas:

```bash
python main.py compare configs/sample.yaml --runs 40 --ttl 4 --csv output/comparacao.csv --chart output/comparacao.png
```

## Configuração

Exemplo:

```yaml
num_nodes: 12
min_neighbors: 2
max_neighbors: 4
resources:
  n1: [r1, r2]
  n2: [r3]
edges:
  - [n1, n2]
```

Os nós são identificados automaticamente como `n1`, `n2`, ..., `nN`, de acordo com `num_nodes`.

## Identificação da equipe

Preencha antes de entregar:

- Nome 1:
- Nome 2:
- Nome 3:
- Nome 4:

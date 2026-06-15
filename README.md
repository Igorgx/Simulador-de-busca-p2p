# Simulador de Busca em Redes P2P

Projeto em Python para simular busca de recursos em redes P2P não estruturadas, conforme o trabalho de Computação Distribuída.

## Funcionalidades

- Leitura de topologias em YAML ou JSON.
- Validação da rede:
  - rede conectada;
  - grau mínimo e máximo por nó;
  - todos os nós com pelo menos um recurso;
  - sem arestas de um nó para ele mesmo.
- Cada nó conhece apenas:
  - seu próprio ID;
  - seus vizinhos;
  - seus recursos locais;
  - seu cache local de localizações aprendidas.
- Busca por inundação (`flooding`).
- Busca por passeio aleatório (`random_walk`).
- Versões informadas com cache (`informed_flooding`, `informed_random_walk`).
- TTL em todas as buscas.
- ID único em cada busca.
- Estatísticas:
  - total de mensagens;
  - total de nós envolvidos;
  - cache hits;
  - caminho do aviso de recurso encontrado;
  - mensagens diretas após descobrir o dono do recurso.
- Rastro escrito passo a passo.
- Visualização da rede e da busca.
- Comparação com mínimo, máximo e média por algoritmo.

## Instalação

```bash
python -m pip install -r requirements.txt
```

## Validação da rede

```bash
python main.py validate configs/sample.yaml
```

## Desenhar a topologia

```bash
python main.py show configs/sample.yaml --output output/rede.png
```

## Executar uma busca com rastro escrito

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo flooding --trace
```

## Executar uma busca com imagem e animação

```bash
python main.py search configs/sample.yaml --origin n1 --resource r11 --ttl 4 --algo informed_flooding --trace --plot output/busca.png --animate output/busca.gif
```

## Demonstrar cache

Execute duas buscas na mesma sessão Python ou use o comando `compare`, que mantém uma rede por algoritmo por padrão para permitir aquecimento do cache.

```bash
python main.py compare configs/sample.yaml --runs 40 --ttl 4 --csv output/comparacao.csv --chart output/comparacao.png
```

Para comparar sem aquecer cache:

```bash
python main.py compare configs/sample.yaml --runs 40 --ttl 4 --cold-cache
```

## Algoritmos

`flooding`: o nó repassa a busca para todos os vizinhos ainda não processados enquanto houver TTL.

`random_walk`: o nó escolhe um vizinho aleatório a cada salto enquanto houver TTL.

`informed_flooding`: igual ao flooding, mas cada nó consulta seu cache antes de retransmitir.

`informed_random_walk`: igual ao random walk, mas cada nó consulta seu cache antes de sortear o próximo vizinho.

Quando o recurso é encontrado, um aviso volta pelo caminho reverso até o nó que iniciou a busca. Os nós no caminho salvam em cache onde o recurso está. Depois disso, o nó de origem pode pedir o recurso diretamente ao nó distante que o possui.

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

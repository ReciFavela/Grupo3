# ♻️ Classificação de Resíduos Plásticos com Machine Learning

## 📌 Descrição

Este projeto desenvolve um pipeline para pré-processamento de imagens e uma camada de ingestão e armazenamento usando bancos não-relacionais para suportar treino e monitoramento de modelos de detecção.

O que está incluído nesta entrega:
- Pipeline de pré-processamento (já existente) — `src/process.py` gera `X.npy`, `y.npy` e `inventario.csv`.
- Infraestrutura local via Docker Compose:
  - MongoDB — armazena eventos brutos de detecção (um documento por frame).
  - InfluxDB — armazena métricas agregadas (contagens por classe, produtividade por turno).
  - MinIO — armazenamento de objetos (imagens). As imagens NÃO são salvas nos bancos, apenas o path no MinIO.
- Worker de ingestão (`src/ingest_worker.py`) com dois modos:
  - `batch`: processa `data/processed/X.npy` + `inventario.csv` e injeta eventos/metricas.
  - `realtime`: processa imagens de um diretório e injeta eventos/metricas.
- Scripts utilitários:
  - `src/database_client.py` — clientes para MongoDB, InfluxDB e MinIO.
  - `src/init_databases.py` — inicializa collections e buckets necessários.
- Testes de integração: `tests/test_integration.py`.

---

## 📂 Estrutura do Projeto (atualizada)

```
projeto-recifavela/
├── docker-compose.yml        # MongoDB, InfluxDB, MinIO
├── .env.example              # Variáveis de ambiente de exemplo
├── requirements.txt          # Dependências Python (inclui clients para DBs)
├── src/
│   ├── process.py            # Pré-processamento (existente)
│   ├── database_client.py    # Clientes para MongoDB/InfluxDB/MinIO
│   ├── init_databases.py     # Script para criar collections/buckets
│   └── ingest_worker.py      # Worker de ingestão (batch + realtime)
├── tests/
│   └── test_integration.py   # Testes de integração
└── data/
    ├── raw/
    └── processed/
        ├── inventario.csv
        ├── X.npy
        └── y.npy
```

---

## 🛠️ Requisitos

- Docker Desktop (macOS) — para subir MongoDB, InfluxDB e MinIO
- Python 3.10+ (recomendado)
- Virtualenv (opcional, recomendado)

Dependências Python atualizadas em `requirements.txt`:
- pymongo
- influxdb-client
- minio
- python-dotenv
- além das bibliotecas já usadas (numpy, pandas, pillow, tqdm, etc.)

---

## 🚀 Fluxo de execução (local de desenvolvimento)

Siga estes passos na raiz do projeto.

1) Criar e ativar o ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Subir os serviços com Docker Compose

```bash
docker compose up -d
# Verificar status
docker ps --format "{{.Names}}: {{.Status}}"
```

3) Inicializar as estruturas nos bancos (collections, buckets)

As variáveis usadas no desenvolvimento/local estão em `.env.example`. Para rodar o script de inicialização:

```bash
# Exemplo (dev):
PYTHONPATH=. MONGO_USERNAME=root MONGO_PASSWORD=rootpassword INFLUXDB_TOKEN=supercalifragilisticexpialidocious .venv/bin/python src/init_databases.py
```

O script cria a collection `detection_events` e `processing_logs` no MongoDB, confirma o bucket `metrics` no InfluxDB e cria o bucket `images` no MinIO.

4) Testes de integração

```bash
PYTHONPATH=. MONGO_USERNAME=root MONGO_PASSWORD=rootpassword INFLUXDB_TOKEN=supercalifragilisticexpialidocious .venv/bin/python tests/test_integration.py
```

5) Executar o worker de ingestão

Batch (processa `data/processed/X.npy`):

```bash
PYTHONPATH=. MONGO_USERNAME=root MONGO_PASSWORD=rootpassword INFLUXDB_TOKEN=supercalifragilisticexpialidocious .venv/bin/python src/ingest_worker.py --mode batch --limit 100
```

Realtime (processa imagens de um diretório):

```bash
PYTHONPATH=. MONGO_USERNAME=root MONGO_PASSWORD=rootpassword INFLUXDB_TOKEN=supercalifragilisticexpialidocious .venv/bin/python src/ingest_worker.py --mode realtime --input-dir /path/to/images --limit 50
```

Observações:
- No modo `batch`, o worker carrega `X.npy`, `y.npy` e `inventario.csv` de `data/processed/`.
- As detecções YOLO atualmente são simuladas (placeholder). Em produção, substitua a função de simulação por integração com o endpoint do detector YOLO.
- O worker faz upload temporário das imagens para o MinIO e grava o caminho retornado no documento do MongoDB.

---

## 📦 Design dos Armazenamentos

- MongoDB (collection `detection_events`)
  - Documento por frame com campos:
    - `timestamp`, `camera_id`, `shift`, `class_predictions` (array), `image_path` (MinIO)
  - Índices criados: `timestamp`, `camera_id`, `shift`, combinados

- InfluxDB (bucket `metrics`)
  - Measurements sugeridos:
    - `detections_per_class` (tags: `class`, `camera_id`, `shift`; field: `count`)
    - `productivity` (tags: `camera_id`, `shift`; field: `frames_processed`)

- MinIO (bucket `images`)
  - Armazena os objetos de imagem; o worker grava o path `bucket/object` no MongoDB.

---

## ✅ Estado atual entregável

- Infraestrutura local via Docker Compose (MongoDB, InfluxDB, MinIO)
- Scripts para inicialização (`src/init_databases.py`)
- Worker de ingestão com modos `batch` e `realtime` (`src/ingest_worker.py`)
- Clientes Python para acessar MongoDB/InfluxDB/MinIO (`src/database_client.py`)
- Testes de integração (`tests/test_integration.py`)

---

## 🔜 Próximos passos sugeridos

- Integrar o worker com o serviço real de inferência YOLO (substituir simulação)
- Adicionar autenticação segura para produção (não usar credenciais padrão)
- Stream de ingestão com filas (RabbitMQ/Kafka) para alto volume
- Adicionar dashboards (Grafana) consultando o InfluxDB

---

## 👨‍💻 Autores

Enzo Oliveira D'Onofrio
Luigi Luand Botto
Luigi Menezes Collesi
Diogo Musso Coutinho
Alan Martins Leandro
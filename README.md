# ♻️ Classificação de Resíduos Plásticos com Machine Learning

## 📌 Descrição

Este projeto tem como objetivo o desenvolvimento de um pipeline de pré-processamento de imagens para classificação de resíduos plásticos utilizando técnicas de Machine Learning.

Nesta primeira etapa, foram utilizados datasets públicos contendo imagens de resíduos para:

- Mapeamento das imagens
- Padronização de tamanho
- Normalização dos dados
- Estruturação para uso em modelos de aprendizado supervisionado

---

## 📂 Estrutura do Projeto

```
PROJETO-RECICLAGEM/
│
├── .venv/                  # Ambiente virtual (ignorado no Git)
│
├── data/
│   ├── raw/                # Dados brutos (datasets originais)
│   │   ├── bottle-synthetic/
│   │   └── realwaste/
│   │
│   └── processed/          # Dados processados
│       ├── inventario.csv  # Mapeamento das imagens
│       ├── X.npy           # Imagens processadas (features)
│       └── y.npy           # Labels das imagens
│
├── src/
│   └── process.py          # Script principal de processamento
│
├── requirements.txt        # Dependências do projeto
└── README.md
```

---

## 🧠 Sobre os Dados

Foram utilizados os seguintes datasets públicos:

- Bottle Synthetic Images Dataset (Kaggle)
- RealWaste Dataset (Kaggle)

As imagens estão organizadas em pastas por classe, permitindo a geração automática de rótulos.

---

## ⚙️ Pipeline de Pré-processamento

O script `process.py` realiza as seguintes etapas:

1. 📁 Leitura dos datasets
2. 🏷️ Criação de inventário
3. 🖼️ Pré-processamento das imagens
   - Conversão para RGB
   - Redimensionamento (128x128)
   - Normalização (valores entre 0 e 1)
4. 🧮 Estruturação dos dados
   - X: array de imagens (N, 128, 128, 3)
   - y: labels correspondentes
5. 💾 Persistência dos dados

---

## ▶️ Como Executar

### 1. Criar e ativar ambiente virtual

```
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### 2. Instalar dependências

```
pip install -r requirements.txt
```

### 3. Executar o processamento

```
python src/process.py
```

---

## 📊 Formato dos Dados Gerados

- X.npy → imagens processadas
- y.npy → labels
- inventario.csv → mapeamento

---

## 🚀 Próximos Passos

- Treinamento de modelos de classificação
- CNN
- Data augmentation
- Avaliação de desempenho

---

## ⚠️ Observações

- Não versionar .venv
- Evitar subir data/raw
- Dados podem ser regenerados

---

## 👨‍💻 Autor

Projeto acadêmico de Machine Learning aplicado à classificação de resíduos.

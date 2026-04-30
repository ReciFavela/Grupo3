import os
import numpy as np
import pandas as pd
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# Configurações
RAIZES_DATASETS = [
    Path("data/raw/bottle-synthetic"),
    Path("data/raw/realwaste")
]

IMG_EXTS = {'.jpg', '.jpeg', '.png'}
IMG_SIZE = (128, 128)

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 1. INVENTÁRIO
# =========================
def criar_inventario(roots):
    registros = []

    for root in roots:
        if not root.exists():
            print(f"Aviso: {root} não existe")
            continue

        for path in root.rglob("*"):
            if path.suffix.lower() in IMG_EXTS and path.is_file():
                classe = path.parent.name
                registros.append({
                    "caminho": str(path),
                    "classe": classe,
                    "arquivo": path.name
                })

    df = pd.DataFrame(registros)

    if not df.empty:
        df["label"] = pd.factorize(df["classe"])[0]

    return df


# =========================
# 2. PRÉ-PROCESSAMENTO
# =========================
def preprocessar_imagem(caminho):
    img = Image.open(caminho).convert("RGB")
    img = img.resize(IMG_SIZE, Image.LANCZOS)
    img = np.array(img, dtype=np.float32) / 255.0
    return img


# =========================
# 3. PIPELINE
# =========================
def processar_dataset():
    df = criar_inventario(RAIZES_DATASETS)

    if df.empty:
        print("Nenhuma imagem encontrada.")
        return

    print(f"Total de imagens: {len(df)}")
    print(f"Classes encontradas: {df['classe'].unique()}")

    X, y = [], []

    for _, row in tqdm(df.iterrows(), total=len(df)):
        try:
            img = preprocessar_imagem(row["caminho"])
            X.append(img)
            y.append(row["label"])
        except Exception as e:
            print(f"Erro: {row['caminho']} -> {e}")

    X = np.array(X)
    y = np.array(y)

    print("\n--- RELATÓRIO ---")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")

    # =========================
    # 4. SALVAMENTO
    # =========================
    np.save(OUTPUT_DIR / "X.npy", X)
    np.save(OUTPUT_DIR / "y.npy", y)
    df.to_csv(OUTPUT_DIR / "inventario.csv", index=False)

    print(f"\nDados salvos em: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    processar_dataset()
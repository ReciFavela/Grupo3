"""
Worker de ingestão de dados - processa imagens e escreve em MongoDB, InfluxDB e MinIO.
Suporta dois modos:
  1. Batch: processa X.npy + inventario.csv
  2. Realtime: processa imagens individuais a partir de um diretório

Usage:
  python src/ingest_worker.py --mode batch [--limit 100]
  python src/ingest_worker.py --mode realtime --input-dir /path/to/images
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any
import tempfile

import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

from src.database_client import MongoDBClient, InfluxDBClient, MinIOClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class IngestWorker:
    """Worker para ingestão de dados nos bancos."""

    def __init__(
        self,
        mongo_uri: str = None,
        influxdb_url: str = None,
        minio_endpoint: str = None
    ):
        """
        Inicializa worker com clientes dos bancos.

        Args:
            mongo_uri: URI do MongoDB
            influxdb_url: URL do InfluxDB
            minio_endpoint: Endpoint do MinIO
        """
        self.mongo = MongoDBClient(uri=mongo_uri)
        self.influx = InfluxDBClient(url=influxdb_url)
        self.minio = MinIOClient(endpoint=minio_endpoint)

        self.processed_count = 0
        self.error_count = 0

    def _generate_mock_detections(self, class_label: int, confidence: float = 0.85) -> List[Dict[str, Any]]:
        """
        Gera detecções simuladas baseadas no label da classe.
        Em produção, isto viria do modelo YOLO.

        Args:
            class_label: Label numérico da classe
            confidence: Confiança da detecção (0-1)

        Returns:
            Lista de detecções simuladas
        """
        # Mapeamento simulado de classes (em produção, vem do modelo YOLO)
        class_names = {
            0: "bottle",
            1: "plastic_bag",
            2: "can",
            3: "paper",
            4: "glass"
        }

        class_name = class_names.get(class_label, f"class_{class_label}")

        # Simula 1-3 detecções por frame
        num_detections = np.random.randint(1, 3)
        detections = []

        for _ in range(num_detections):
            detections.append({
                "class": class_name,
                "confidence": round(confidence + np.random.uniform(-0.1, 0.05), 3),
                "bbox": {
                    "x": int(np.random.uniform(0, 128)),
                    "y": int(np.random.uniform(0, 128)),
                    "width": int(np.random.uniform(20, 100)),
                    "height": int(np.random.uniform(20, 100))
                }
            })

        return detections

    def _upload_image_array(
        self,
        image_array: np.ndarray,
        camera_id: str,
        shift: str,
        timestamp: datetime
    ) -> str:
        """
        Converte array numpy em arquivo temporário e faz upload para MinIO.

        Args:
            image_array: Array numpy (H, W, 3) com valores 0-1
            camera_id: ID da câmera
            shift: Turno
            timestamp: Timestamp

        Returns:
            Path no MinIO
        """
        try:
            # Converter array para imagem PIL
            # O array vem normalizado (0-1), converter para 0-255
            img_array = (image_array * 255).astype(np.uint8)
            img = Image.fromarray(img_array)

            # Salvar em arquivo temporário
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
                img.save(tmp_path, format="JPEG")

            # Upload para MinIO
            timestamp_unix = int(timestamp.timestamp())
            object_name = f"camera_{camera_id}/shift_{shift}/{timestamp_unix}.jpg"

            minio_path = self.minio.upload_image(tmp_path, object_name)

            # Deletar arquivo temporário
            os.unlink(tmp_path)

            return minio_path

        except Exception as e:
            logger.error(f"Erro ao fazer upload de imagem: {e}")
            raise

    def _save_detection_event(
        self,
        timestamp: datetime,
        camera_id: str,
        shift: str,
        class_predictions: List[Dict[str, Any]],
        image_path: str,
        inventario_row: Dict[str, Any] = None
    ) -> str:
        """
        Salva evento de detecção em MongoDB.

        Args:
            timestamp: Timestamp do processamento
            camera_id: ID da câmera
            shift: Turno
            class_predictions: Detecções YOLO
            image_path: Path da imagem no MinIO
            inventario_row: Dados adicionais do inventário

        Returns:
            ID do documento inserido
        """
        doc_id = self.mongo.insert_detection(
            collection_name="detection_events",
            timestamp=timestamp,
            camera_id=camera_id,
            shift=shift,
            class_predictions=class_predictions,
            image_path=image_path,
            # Campos adicionais
            inventario_file=inventario_row.get("arquivo") if inventario_row else None,
            original_class=inventario_row.get("classe") if inventario_row else None
        )

        return doc_id

    def _save_metrics(
        self,
        timestamp: datetime,
        camera_id: str,
        shift: str,
        class_predictions: List[Dict[str, Any]]
    ):
        """
        Salva métricas em InfluxDB.

        Args:
            timestamp: Timestamp
            camera_id: ID da câmera
            shift: Turno
            class_predictions: Detecções (para contar por classe)
        """
        # Métrica 1: Contagem por classe
        class_counts = {}
        for detection in class_predictions:
            class_name = detection["class"]
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

        for class_name, count in class_counts.items():
            self.influx.write_metric(
                measurement="detections_per_class",
                fields={"count": count},
                tags={
                    "class": class_name,
                    "camera_id": camera_id,
                    "shift": shift
                },
                timestamp=timestamp
            )

        # Métrica 2: Produtividade (frames processados por turno)
        self.influx.write_metric(
            measurement="productivity",
            fields={"frames_processed": 1},
            tags={
                "camera_id": camera_id,
                "shift": shift
            },
            timestamp=timestamp
        )

    def ingest_batch(self, limit: int = None):
        """
        Processa dados em batch a partir de X.npy + inventario.csv.

        Args:
            limit: Limite de imagens a processar (None = todas)
        """
        logger.info("=" * 70)
        logger.info("INICIANDO INGESTÃO EM BATCH")
        logger.info("=" * 70)

        # Caminhos esperados
        X_path = Path("data/processed/X.npy")
        y_path = Path("data/processed/y.npy")
        inventario_path = Path("data/processed/inventario.csv")

        # Validar arquivos
        if not X_path.exists():
            logger.error(f"✗ Arquivo não encontrado: {X_path}")
            return False

        if not y_path.exists():
            logger.error(f"✗ Arquivo não encontrado: {y_path}")
            return False

        if not inventario_path.exists():
            logger.error(f"✗ Arquivo não encontrado: {inventario_path}")
            return False

        try:
            # Carregar dados
            logger.info("  📦 Carregando X.npy...")
            X = np.load(X_path)
            logger.info(f"    Shape: {X.shape}")

            logger.info("  📦 Carregando y.npy...")
            y = np.load(y_path)
            logger.info(f"    Shape: {y.shape}")

            logger.info("  📦 Carregando inventario.csv...")
            df = pd.read_csv(inventario_path)
            logger.info(f"    Registros: {len(df)}")

            # Aplicar limite se especificado
            if limit:
                X = X[:limit]
                y = y[:limit]
                df = df[:limit]
                logger.info(f"  📌 Processando apenas {limit} primeiras imagens")

            # Parametrização de câmera e turno (em produção, viriam de metadados)
            camera_ids = ["camera_001", "camera_002"]  # Simulado
            shifts = ["turno_1", "turno_2"]  # Simulado

            # Processamento
            logger.info(f"\n  ⏳ Processando {len(X)} imagens...\n")

            for idx in tqdm(range(len(X)), desc="Ingestão"):
                try:
                    # Dados
                    image_array = X[idx]
                    label = y[idx]
                    inventario_row = df.iloc[idx].to_dict()

                    # Simular timestamp (cada frame é ~33ms atrás, como em video real)
                    timestamp = datetime.utcnow() - timedelta(milliseconds=idx * 33)

                    # Selecionar câmera e turno circulamente
                    camera_id = camera_ids[idx % len(camera_ids)]
                    shift = shifts[(idx // len(camera_ids)) % len(shifts)]

                    # 1. Upload para MinIO
                    image_path = self._upload_image_array(
                        image_array,
                        camera_id=camera_id,
                        shift=shift,
                        timestamp=timestamp
                    )

                    # 2. Gerar detecções simuladas (de YOLO)
                    class_predictions = self._generate_mock_detections(int(label))

                    # 3. Salvar em MongoDB
                    doc_id = self._save_detection_event(
                        timestamp=timestamp,
                        camera_id=camera_id,
                        shift=shift,
                        class_predictions=class_predictions,
                        image_path=image_path,
                        inventario_row=inventario_row
                    )

                    # 4. Salvar métricas em InfluxDB
                    self._save_metrics(
                        timestamp=timestamp,
                        camera_id=camera_id,
                        shift=shift,
                        class_predictions=class_predictions
                    )

                    self.processed_count += 1

                except Exception as e:
                    logger.warning(f"⚠ Erro ao processar índice {idx}: {e}")
                    self.error_count += 1

            logger.info("\n" + "=" * 70)
            logger.info("RESUMO DA INGESTÃO EM BATCH")
            logger.info("=" * 70)
            logger.info(f"✓ Processadas com sucesso: {self.processed_count}")
            logger.info(f"✗ Erros: {self.error_count}")
            logger.info(f"📊 Taxa de sucesso: {(self.processed_count / (self.processed_count + self.error_count) * 100):.1f}%")

            return self.error_count == 0

        except Exception as e:
            logger.error(f"✗ Erro fatal ao processar batch: {e}")
            return False

    def ingest_realtime(self, input_dir: str, limit: int = None):
        """
        Processa imagens de um diretório (tempo real simulado).

        Args:
            input_dir: Diretório com imagens
            limit: Limite de imagens
        """
        logger.info("=" * 70)
        logger.info("INICIANDO INGESTÃO EM TEMPO REAL")
        logger.info(f"Diretório de entrada: {input_dir}")
        logger.info("=" * 70)

        input_path = Path(input_dir)

        if not input_path.exists():
            logger.error(f"✗ Diretório não encontrado: {input_dir}")
            return False

        # Listar imagens
        image_files = list(input_path.glob("**/*.jpg")) + \
                      list(input_path.glob("**/*.png")) + \
                      list(input_path.glob("**/*.jpeg"))

        if not image_files:
            logger.error(f"✗ Nenhuma imagem encontrada em {input_dir}")
            return False

        if limit:
            image_files = image_files[:limit]

        logger.info(f"  📦 Encontradas {len(image_files)} imagens\n")

        camera_ids = ["camera_001", "camera_002"]
        shifts = ["turno_1", "turno_2"]

        try:
            for idx, image_file in enumerate(tqdm(image_files, desc="Ingestão realtime")):
                try:
                    # Carregar imagem
                    img = Image.open(image_file).convert("RGB")
                    img = img.resize((128, 128), Image.LANCZOS)
                    image_array = np.array(img, dtype=np.float32) / 255.0

                    # Simular label (0-4)
                    label = idx % 5

                    # Timestamp
                    timestamp = datetime.utcnow()

                    # Câmera e turno
                    camera_id = camera_ids[idx % len(camera_ids)]
                    shift = shifts[(idx // len(camera_ids)) % len(shifts)]

                    # 1. Upload para MinIO
                    image_path = self._upload_image_array(
                        image_array,
                        camera_id=camera_id,
                        shift=shift,
                        timestamp=timestamp
                    )

                    # 2. Gerar detecções
                    class_predictions = self._generate_mock_detections(label)

                    # 3. MongoDB
                    self._save_detection_event(
                        timestamp=timestamp,
                        camera_id=camera_id,
                        shift=shift,
                        class_predictions=class_predictions,
                        image_path=image_path,
                        inventario_row={"arquivo": image_file.name}
                    )

                    # 4. InfluxDB
                    self._save_metrics(
                        timestamp=timestamp,
                        camera_id=camera_id,
                        shift=shift,
                        class_predictions=class_predictions
                    )

                    self.processed_count += 1

                except Exception as e:
                    logger.warning(f"⚠ Erro ao processar {image_file}: {e}")
                    self.error_count += 1

            logger.info("\n" + "=" * 70)
            logger.info("RESUMO DA INGESTÃO EM TEMPO REAL")
            logger.info("=" * 70)
            logger.info(f"✓ Processadas com sucesso: {self.processed_count}")
            logger.info(f"✗ Erros: {self.error_count}")

            return self.error_count == 0

        except Exception as e:
            logger.error(f"✗ Erro fatal ao processar realtime: {e}")
            return False

    def close(self):
        """Fecha conexões com os bancos."""
        self.mongo.close()
        self.influx.close()
        self.minio.close()


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Worker de ingestão de dados - MongoDB, InfluxDB, MinIO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Processar batch (X.npy + inventario.csv)
  python src/ingest_worker.py --mode batch

  # Processar apenas 50 imagens do batch
  python src/ingest_worker.py --mode batch --limit 50

  # Processar imagens de um diretório
  python src/ingest_worker.py --mode realtime --input-dir /path/to/images
        """
    )

    parser.add_argument(
        "--mode",
        choices=["batch", "realtime"],
        required=True,
        help="Modo de ingestão"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite de imagens a processar"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Diretório de entrada (obrigatório para modo realtime)"
    )

    args = parser.parse_args()

    # Validações
    if args.mode == "realtime" and not args.input_dir:
        parser.error("--input-dir é obrigatório no modo realtime")

    # Executar
    worker = IngestWorker()

    try:
        if args.mode == "batch":
            success = worker.ingest_batch(limit=args.limit)
        else:  # realtime
            success = worker.ingest_realtime(args.input_dir, limit=args.limit)

        worker.close()
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("\n⏸ Ingestão interrompida pelo usuário")
        worker.close()
        return 1
    except Exception as e:
        logger.error(f"✗ Erro não tratado: {e}")
        worker.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())

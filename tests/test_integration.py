"""
Testes de integração para validar conexões com MongoDB, InfluxDB e MinIO.
Execute após docker-compose up e init_databases.py.

Usage:
  python -m pytest tests/test_integration.py -v
  ou
  python tests/test_integration.py
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

from src.database_client import MongoDBClient, InfluxDBClient, MinIOClient


class TestIntegration:
    """Testes de integração dos bancos."""

    @staticmethod
    def test_mongodb_connection():
        """Testa conexão com MongoDB."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: MongoDB Connection")
        logger.info("=" * 70)

        try:
            mongo = MongoDBClient()
            logger.info("✓ Conexão estabelecida")

            # Teste: listar collections
            collections = mongo.db.list_collection_names()
            logger.info(f"✓ Collections encontradas: {collections}")

            # Teste: contar documentos
            count = mongo.db.detection_events.count_documents({})
            logger.info(f"✓ Documentos em detection_events: {count}")

            mongo.close()
            logger.info("✓ Desconectado com sucesso")
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def test_mongodb_insert():
        """Testa inserção em MongoDB."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: MongoDB Insert")
        logger.info("=" * 70)

        try:
            mongo = MongoDBClient()

            # Inserir documento teste
            doc_id = mongo.insert_detection(
                collection_name="detection_events",
                timestamp=datetime.utcnow(),
                camera_id="test_camera",
                shift="test_shift",
                class_predictions=[
                    {"class": "bottle", "confidence": 0.95},
                    {"class": "plastic_bag", "confidence": 0.82}
                ],
                image_path="test_bucket/test_image.jpg"
            )

            logger.info(f"✓ Documento inserido: {doc_id}")

            # Buscar documento
            found = mongo.find_detections(
                "detection_events",
                query={"_id": doc_id.__class__(doc_id)},
                limit=1
            )

            if found:
                logger.info(f"✓ Documento recuperado: {found[0]['camera_id']}")
            else:
                logger.warning("⚠ Documento não encontrado na busca")

            mongo.close()
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def test_influxdb_connection():
        """Testa conexão com InfluxDB."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: InfluxDB Connection")
        logger.info("=" * 70)

        try:
            influx = InfluxDBClient()
            logger.info(f"✓ Conexão estabelecida")
            logger.info(f"✓ URL: {influx.url}")
            logger.info(f"✓ Org: {influx.org}")
            logger.info(f"✓ Bucket: {influx.bucket}")

            influx.close()
            logger.info("✓ Desconectado com sucesso")
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def test_influxdb_write():
        """Testa escrita em InfluxDB."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: InfluxDB Write")
        logger.info("=" * 70)

        try:
            influx = InfluxDBClient()

            # Escrever métrica teste
            influx.write_metric(
                measurement="test_measurement",
                fields={"value": 42.5},
                tags={"test": "integration"},
                timestamp=datetime.utcnow()
            )

            logger.info("✓ Métrica escrita com sucesso")

            influx.close()
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def test_minio_connection():
        """Testa conexão com MinIO."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: MinIO Connection")
        logger.info("=" * 70)

        try:
            minio = MinIOClient()
            logger.info(f"✓ Conexão estabelecida")
            logger.info(f"✓ Endpoint: {minio.endpoint}")
            logger.info(f"✓ Bucket padrão: {minio.bucket}")

            # Listar buckets (list returned by minio.list_buckets)
            buckets = minio.client.list_buckets()
            bucket_names = [b.name for b in buckets]
            logger.info(f"✓ Buckets disponíveis: {bucket_names}")

            minio.close()
            logger.info("✓ Desconectado com sucesso")
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def test_minio_upload():
        """Testa upload em MinIO."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST: MinIO Upload")
        logger.info("=" * 70)

        try:
            from PIL import Image
            import numpy as np
            import tempfile
            import os

            minio = MinIOClient()

            # Criar imagem teste
            test_array = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
            test_img = Image.fromarray(test_array)

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
                test_img.save(tmp_path, format="JPEG")

            # Upload
            minio_path = minio.upload_image(
                tmp_path,
                "test_uploads/integration_test.jpg"
            )

            logger.info(f"✓ Imagem uploaded: {minio_path}")

            # Listar objetos
            objects = minio.list_objects("images", prefix="test_uploads")
            logger.info(f"✓ Objetos com prefixo 'test_uploads': {len(objects)}")

            # Cleanup
            os.unlink(tmp_path)

            minio.close()
            return True

        except Exception as e:
            logger.error(f"✗ Erro: {e}")
            return False

    @staticmethod
    def run_all():
        """Executa todos os testes."""
        logger.info("\n")
        logger.info("╔" + "=" * 68 + "╗")
        logger.info("║" + " " * 68 + "║")
        logger.info("║" + "  TESTES DE INTEGRAÇÃO".center(68) + "║")
        logger.info("║" + "  MongoDB + InfluxDB + MinIO".center(68) + "║")
        logger.info("║" + " " * 68 + "║")
        logger.info("╚" + "=" * 68 + "╝")

        tests = [
            ("MongoDB Connection", TestIntegration.test_mongodb_connection),
            ("MongoDB Insert", TestIntegration.test_mongodb_insert),
            ("InfluxDB Connection", TestIntegration.test_influxdb_connection),
            ("InfluxDB Write", TestIntegration.test_influxdb_write),
            ("MinIO Connection", TestIntegration.test_minio_connection),
            ("MinIO Upload", TestIntegration.test_minio_upload),
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = "PASSOU" if result else "FALHOU"
            except Exception as e:
                logger.error(f"Exception em {test_name}: {e}")
                results[test_name] = "ERRO"

        # Resumo
        logger.info("\n" + "=" * 70)
        logger.info("RESUMO DOS TESTES")
        logger.info("=" * 70)

        for test_name, result in results.items():
            symbol = "✓" if result == "PASSOU" else "✗"
            logger.info(f"{symbol} {test_name:40s} {result:15s}")

        logger.info("=" * 70)

        # Retornar código de saída
        failed = sum(1 for r in results.values() if r != "PASSOU")
        if failed == 0:
            logger.info("\n✓ Todos os testes passaram!")
            return 0
        else:
            logger.error(f"\n✗ {failed} teste(s) falharam")
            return 1


def main():
    """Função principal para execução direta."""
    return TestIntegration.run_all()


if __name__ == "__main__":
    sys.exit(main())

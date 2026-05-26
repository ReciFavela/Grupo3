"""
Script para inicializar estruturas nos bancos de dados.
Cria collections no MongoDB, buckets no MinIO, e configura InfluxDB.
Execute após subir os serviços com docker-compose.
"""

import logging
import sys
from datetime import datetime

from src.database_client import MongoDBClient, InfluxDBClient, MinIOClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_mongodb():
    """Inicializa MongoDB com collections e índices."""
    logger.info("=" * 60)
    logger.info("INICIALIZANDO MONGODB")
    logger.info("=" * 60)

    try:
        mongo = MongoDBClient()

        # Collection: detection_events
        # Armazena eventos brutos de detecção (um documento por frame)
        mongo.create_collection(
            "detection_events",
            indexes=[
                ["timestamp"],
                ["camera_id"],
                ["shift"],
                ["camera_id", "shift"],
                ["timestamp", "camera_id"]
            ]
        )

        # Collection: processing_logs (opcional, para auditoria)
        mongo.create_collection(
            "processing_logs",
            indexes=[
                ["timestamp"],
                ["worker_id"],
            ]
        )

        # Exibir estatísticas
        stats = mongo.get_collection_stats("detection_events")
        logger.info(f"  Estatísticas: {stats['count']} documentos na collection")

        mongo.close()
        logger.info("✓ MongoDB inicializado com sucesso\n")
        return True

    except Exception as e:
        logger.error(f"✗ Erro ao inicializar MongoDB: {e}\n")
        return False


def init_influxdb():
    """Inicializa InfluxDB com buckets e organizações."""
    logger.info("=" * 60)
    logger.info("INICIALIZANDO INFLUXDB")
    logger.info("=" * 60)

    try:
        influx = InfluxDBClient()

        # O bucket 'metrics' já é criado no docker-compose.yml
        # Apenas confirmamos que está acessível
        logger.info(f"✓ Conectado ao bucket: {influx.bucket}")

        # Teste: escrever uma métrica de inicialização
        influx.write_metric(
            measurement="initialization",
            fields={"status": 1},
            tags={"service": "influxdb"},
            timestamp=datetime.utcnow()
        )

        logger.info("  ✓ Teste de escrita: sucesso")

        influx.close()
        logger.info("✓ InfluxDB inicializado com sucesso\n")
        return True

    except Exception as e:
        logger.error(f"✗ Erro ao inicializar InfluxDB: {e}\n")
        return False


def init_minio():
    """Inicializa MinIO com buckets."""
    logger.info("=" * 60)
    logger.info("INICIALIZANDO MINIO")
    logger.info("=" * 60)

    try:
        minio = MinIOClient()

        # Criar bucket 'images' para armazenar imagens
        minio.create_bucket("images")

        # Listar objetos no bucket para confirmar acesso
        objects = minio.list_objects("images")
        logger.info(f"  ✓ Bucket 'images' contém {len(objects)} objetos")

        minio.close()
        logger.info("✓ MinIO inicializado com sucesso\n")
        return True

    except Exception as e:
        logger.error(f"✗ Erro ao inicializar MinIO: {e}\n")
        return False


def main():
    """Executa inicialização completa de todos os bancos."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 58 + "║")
    logger.info("║" + "  INICIALIZAÇÃO DE BANCOS DE DADOS".center(58) + "║")
    logger.info("║" + "  Projeto Recifavela - IA & Waste Management".center(58) + "║")
    logger.info("║" + " " * 58 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("\n")

    results = {
        "MongoDB": init_mongodb(),
        "InfluxDB": init_influxdb(),
        "MinIO": init_minio()
    }

    logger.info("=" * 60)
    logger.info("RESUMO DE INICIALIZAÇÃO")
    logger.info("=" * 60)

    all_success = True
    for service, success in results.items():
        status = "✓ SUCESSO" if success else "✗ ERRO"
        logger.info(f"{service:15s}: {status}")
        if not success:
            all_success = False

    logger.info("=" * 60)

    if all_success:
        logger.info("\n✓ Todos os bancos foram inicializados com sucesso!")
        logger.info("  Você pode agora executar: python src/ingest_worker.py --mode batch\n")
        return 0
    else:
        logger.error("\n✗ Alguns bancos falharam na inicialização.")
        logger.error("  Verifique se docker-compose está rodando: docker-compose ps\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

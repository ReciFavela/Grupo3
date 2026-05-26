"""
Database clients para integração com MongoDB, InfluxDB e MinIO.
Fornece interfaces unificadas para operações em cada banco.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from influxdb_client import InfluxDBClient as InfluxNativeClient
from influxdb_client.client.write_api import SYNCHRONOUS
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MongoDBClient:
    """Cliente para operações em MongoDB."""

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        db_name: str = "detection_db",
        timeout: int = 5000
    ):
        """
        Inicializa conexão com MongoDB.

        Args:
            uri: String de conexão MongoDB (ex: mongodb://localhost:27017)
            username: Usuário para autenticação
            password: Senha para autenticação
            db_name: Nome do banco de dados
            timeout: Timeout em ms para operações
        """
        self.uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.username = username or os.getenv("MONGO_USERNAME")
        self.password = password or os.getenv("MONGO_PASSWORD")
        self.db_name = db_name or os.getenv("MONGO_DB_NAME", "detection_db")
        self.timeout = timeout

        self.client = None
        self.db = None
        self._connect()

    def _connect(self):
        """Estabelece conexão com MongoDB."""
        try:
            if self.username and self.password:
                self.client = MongoClient(
                    self.uri,
                    username=self.username,
                    password=self.password,
                    serverSelectionTimeoutMS=self.timeout,
                    connectTimeoutMS=self.timeout
                )
            else:
                self.client = MongoClient(
                    self.uri,
                    serverSelectionTimeoutMS=self.timeout,
                    connectTimeoutMS=self.timeout
                )

            # Testa conexão
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            logger.info(f"✓ Conectado ao MongoDB: {self.db_name}")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"✗ Erro ao conectar ao MongoDB: {e}")
            raise

    def close(self):
        """Fecha conexão com MongoDB."""
        if self.client:
            self.client.close()
            logger.info("MongoDB conexão fechada")

    def create_collection(self, collection_name: str, indexes: List[List[str]] = None):
        """
        Cria uma collection e aplica índices.

        Args:
            collection_name: Nome da collection
            indexes: Lista de listas de campos para índices (ex: [["timestamp"], ["camera_id", "shift"]])
        """
        if collection_name not in self.db.list_collection_names():
            self.db.create_collection(collection_name)
            logger.info(f"✓ Collection '{collection_name}' criada")
        else:
            logger.info(f"⚠ Collection '{collection_name}' já existe")

        if indexes:
            collection = self.db[collection_name]
            for index_fields in indexes:
                index_list = [(field, pymongo.ASCENDING) for field in index_fields]
                try:
                    collection.create_index(index_list)
                    logger.info(f"  ✓ Índice criado em {index_fields}")
                except Exception as e:
                    logger.warning(f"  ⚠ Erro ao criar índice {index_fields}: {e}")

    def insert_detection(
        self,
        collection_name: str,
        timestamp: datetime,
        camera_id: str,
        shift: str,
        class_predictions: List[Dict[str, Any]],
        image_path: str,
        **kwargs
    ) -> str:
        """
        Insere evento de detecção em MongoDB.

        Args:
            collection_name: Nome da collection
            timestamp: Timestamp do processamento
            camera_id: ID da câmera
            shift: Turno de operação
            class_predictions: Lista de detecções YOLO [{"class": "bottle", "confidence": 0.95}]
            image_path: Caminho da imagem no MinIO
            **kwargs: Campos adicionais

        Returns:
            ID do documento inserido
        """
        collection = self.db[collection_name]

        document = {
            "timestamp": timestamp,
            "camera_id": camera_id,
            "shift": shift,
            "class_predictions": class_predictions,
            "image_path": image_path,
            "inserted_at": datetime.utcnow(),
            **kwargs
        }

        result = collection.insert_one(document)
        logger.debug(f"✓ Documento inserido em MongoDB: {result.inserted_id}")
        return str(result.inserted_id)

    def find_detections(
        self,
        collection_name: str,
        query: Dict[str, Any] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Busca documentos em MongoDB.

        Args:
            collection_name: Nome da collection
            query: Filtro (ex: {"camera_id": "cam_1"})
            limit: Limite de resultados

        Returns:
            Lista de documentos
        """
        collection = self.db[collection_name]
        query = query or {}

        results = list(collection.find(query).limit(limit))
        logger.debug(f"✓ {len(results)} documentos encontrados")
        return results

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Retorna estatísticas da collection."""
        collection = self.db[collection_name]
        return {
            "count": collection.count_documents({}),
            "name": collection_name
        }


class InfluxDBClient:
    """Cliente para operações em InfluxDB."""

    def __init__(
        self,
        url: str = None,
        token: str = None,
        org: str = None,
        bucket: str = None
    ):
        """
        Inicializa conexão com InfluxDB.

        Args:
            url: URL do InfluxDB (ex: http://localhost:8086)
            token: Token de autenticação
            org: Organização
            bucket: Bucket padrão
        """
        self.url = url or os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.token = token or os.getenv("INFLUXDB_TOKEN")
        self.org = org or os.getenv("INFLUXDB_ORG", "projeto-recifavela")
        self.bucket = bucket or os.getenv("INFLUXDB_BUCKET", "metrics")

        self.client = None
        self.write_api = None
        self._connect()

    def _connect(self):
        """Estabelece conexão com InfluxDB."""
        try:
            # Note: influxdb-client's InfluxDBClient does not accept a 'timeout'
            # keyword in some versions; avoid passing it to remain compatible.
            # Use the native InfluxDB client (aliased) to avoid colliding
            # with this wrapper class name.
            self.client = InfluxNativeClient(
                url=self.url,
                token=self.token,
                org=self.org
            )

            # Testa conexão
            self.client.ping()
            self.write_api = self.client.write_api(write_type=SYNCHRONOUS)
            logger.info(f"✓ Conectado ao InfluxDB: {self.bucket}")

        except Exception as e:
            logger.error(f"✗ Erro ao conectar ao InfluxDB: {e}")
            raise

    def close(self):
        """Fecha conexão com InfluxDB."""
        # Fechar write_api se disponível para evitar erros de shutdown
        try:
            if hasattr(self, "write_api") and self.write_api is not None:
                if hasattr(self.write_api, "close"):
                    self.write_api.close()
        except Exception:
            pass

        if self.client:
            try:
                self.client.close()
            except Exception:
                pass

        logger.info("InfluxDB conexão fechada")

    def write_metric(
        self,
        measurement: str,
        fields: Dict[str, Any],
        tags: Dict[str, str] = None,
        timestamp: datetime = None
    ):
        """
        Escreve métrica em InfluxDB.

        Args:
            measurement: Nome do measurement
            fields: Dicionário de fields (valores numéricos)
            tags: Dicionário de tags (metadados)
            timestamp: Timestamp (padrão: agora)
        """
        tags = tags or {}
        timestamp = timestamp or datetime.utcnow()

        # Constrói ponto em formato Line Protocol
        tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
        field_str = ",".join([f"{k}={v}" for k, v in fields.items()])

        if tag_str:
            line = f"{measurement},{tag_str} {field_str} {int(timestamp.timestamp() * 1e9)}"
        else:
            line = f"{measurement} {field_str} {int(timestamp.timestamp() * 1e9)}"

        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=line)
            logger.debug(f"✓ Métrica escrita: {measurement}")
        except Exception as e:
            logger.error(f"✗ Erro ao escrever métrica: {e}")
            raise

    def query_bucket(self, query: str) -> List[Dict]:
        """
        Executa query Flux no InfluxDB.

        Args:
            query: Query em linguagem Flux

        Returns:
            Resultados da query
        """
        try:
            query_api = self.client.query_api()
            result = query_api.query(org=self.org, query=query)
            logger.debug(f"✓ Query executada com sucesso")
            return result
        except Exception as e:
            logger.error(f"✗ Erro ao executar query: {e}")
            raise


class MinIOClient:
    """Cliente para operações em MinIO."""

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        use_ssl: bool = False,
        bucket: str = None
    ):
        """
        Inicializa conexão com MinIO.

        Args:
            endpoint: Endpoint do MinIO (ex: localhost:9000)
            access_key: Access key
            secret_key: Secret key
            use_ssl: Usar SSL
            bucket: Bucket padrão
        """
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.use_ssl = use_ssl or os.getenv("MINIO_USE_SSL", "false").lower() == "true"
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "images")

        self.client = None
        self._connect()

    def _connect(self):
        """Estabelece conexão com MinIO."""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.use_ssl
            )

            # Testa conexão
            self.client.list_buckets()
            logger.info(f"✓ Conectado ao MinIO: {self.endpoint}")

        except Exception as e:
            logger.error(f"✗ Erro ao conectar ao MinIO: {e}")
            raise

    def close(self):
        """Fecha conexão com MinIO (não necessário para MinIO HTTP)."""
        logger.info("MinIO desconectado")

    def create_bucket(self, bucket_name: str = None):
        """
        Cria bucket no MinIO.

        Args:
            bucket_name: Nome do bucket (padrão: self.bucket)
        """
        bucket_name = bucket_name or self.bucket

        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"✓ Bucket '{bucket_name}' criado")
            else:
                logger.info(f"⚠ Bucket '{bucket_name}' já existe")
        except S3Error as e:
            logger.error(f"✗ Erro ao criar bucket: {e}")
            raise

    def upload_image(
        self,
        file_path: str,
        object_name: str,
        bucket_name: str = None
    ) -> str:
        """
        Upload de imagem para MinIO.

        Args:
            file_path: Caminho local do arquivo
            object_name: Nome do objeto no MinIO (ex: camera_1/shift_1/timestamp.jpg)
            bucket_name: Nome do bucket

        Returns:
            Path completo do objeto no MinIO
        """
        bucket_name = bucket_name or self.bucket

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

            file_size = os.path.getsize(file_path)

            with open(file_path, "rb") as file_data:
                self.client.put_object(
                    bucket_name,
                    object_name,
                    file_data,
                    length=file_size
                )

            logger.debug(f"✓ Imagem uploaded: {object_name}")
            return f"{bucket_name}/{object_name}"

        except Exception as e:
            logger.error(f"✗ Erro ao fazer upload: {e}")
            raise

    def list_objects(self, bucket_name: str = None, prefix: str = None) -> List[str]:
        """
        Lista objetos em um bucket.

        Args:
            bucket_name: Nome do bucket
            prefix: Prefixo para filtrar

        Returns:
            Lista de nomes de objetos
        """
        bucket_name = bucket_name or self.bucket

        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"✗ Erro ao listar objetos: {e}")
            raise

    def get_object_url(
        self,
        object_name: str,
        bucket_name: str = None,
        expiration: int = 7200
    ) -> str:
        """
        Gera URL pública para acesso ao objeto.

        Args:
            object_name: Nome do objeto
            bucket_name: Nome do bucket
            expiration: Tempo de expiração em segundos

        Returns:
            URL pública
        """
        bucket_name = bucket_name or self.bucket

        try:
            url = self.client.get_presigned_url(
                "GET",
                bucket_name,
                object_name,
                expires=expiration
            )
            return url
        except Exception as e:
            logger.error(f"✗ Erro ao gerar URL: {e}")
            raise

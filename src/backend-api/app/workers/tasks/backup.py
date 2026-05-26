"""Backup Celery task (Story 9-4)."""

import os
import subprocess
import tempfile
from datetime import datetime, timezone

import structlog

from app.workers import celery_app

log = structlog.get_logger()


@celery_app.task(name="backup.run_backup", bind=True, max_retries=2)
def run_backup(self) -> dict:
    """Run pg_dump, compress, and upload to S3/MinIO."""
    from app.infrastructure.settings import get_settings

    settings = get_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    filename = f"backup-{timestamp}.dump.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        dump_path = os.path.join(tmpdir, filename)

        # Parse DATABASE_URL for pg_dump (convert async URL to sync)
        db_url = settings.DATABASE_URL.replace("+asyncpg", "")

        try:
            # pg_dump with custom format + compression
            cmd = [
                "pg_dump",
                "--format=custom",
                "--compress=9",
                f"--file={dump_path}",
                db_url,
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            log.info("backup_dump_completed", filename=filename)
        except subprocess.CalledProcessError as e:
            log.error("backup_dump_failed", error=e.stderr.decode() if e.stderr else str(e))
            raise self.retry(exc=e, countdown=60)
        except FileNotFoundError:
            log.warning("pg_dump_not_available", msg="pg_dump binary not found, skipping backup")
            return {"status": "skipped", "reason": "pg_dump not available"}

        # Upload to S3/MinIO
        try:
            import boto3
            from botocore.config import Config as BotoConfig

            s3 = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=BotoConfig(signature_version="s3v4"),
            )

            s3_key = f"backups/{filename}"
            file_size = os.path.getsize(dump_path)
            s3.upload_file(dump_path, settings.S3_BUCKET, s3_key)
            s3.close()

            log.info("backup_uploaded", key=s3_key, size=file_size)

            return {
                "status": "success",
                "filename": filename,
                "s3_key": s3_key,
                "size": file_size,
            }
        except Exception as e:
            log.error("backup_upload_failed", error=str(e))
            raise self.retry(exc=e, countdown=60)
